"""
Audit Log API Routes.

Persists all audit events to the audit_logs PostgreSQL table.
Replaces the previous in-memory list — entries survive API restarts.

Endpoints:
    GET /api/v1/audit/        — paginated audit log (admin only)
    GET /api/v1/audit/export  — CSV export of all entries (admin only)

Middleware:
    audit_middleware(request, call_next) — records one row per API request
"""
from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routes.deps import get_db, require_roles
from src.database.models import AuditLog

log = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/audit",
    tags=["Audit"],
    dependencies=[Depends(require_roles("admin"))],
)


# ── Public helper (called from middleware and other routes) ────────────────

async def record(
    user: str,
    action: str,
    resource: str,
    detail: str = "",
    ip: str = "",
) -> None:
    """Persist one audit event to the database. Never raises — logs on failure."""
    from src.database.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as session:
            session.add(AuditLog(
                user=user,
                action=action,
                resource=resource,
                detail=detail or None,
                ip=ip or None,
            ))
            await session.commit()
    except Exception as exc:
        log.warning("audit record failed: %s", exc)


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_audit(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    q = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if search:
        pattern = f"%{search}%"
        q = q.where(
            or_(
                AuditLog.user.ilike(pattern),
                AuditLog.action.ilike(pattern),
                AuditLog.resource.ilike(pattern),
                AuditLog.detail.ilike(pattern),
            )
        )

    total_q = select(func.count()).select_from(q.subquery())
    total: int = (await db.execute(total_q)).scalar_one()

    rows = (
        await db.execute(q.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    items = [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "user": r.user,
            "action": r.action,
            "resource": r.resource,
            "detail": r.detail or "",
            "ip": r.ip or "",
        }
        for r in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/export")
async def export_audit(db: AsyncSession = Depends(get_db)) -> Response:
    """Return all audit log entries as CSV."""
    rows = (
        await db.execute(select(AuditLog).order_by(AuditLog.timestamp.desc()))
    ).scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "timestamp", "user", "action", "resource", "detail", "ip"])
    for r in rows:
        writer.writerow([
            r.id,
            r.timestamp.isoformat() if r.timestamp else "",
            r.user, r.action, r.resource,
            r.detail or "", r.ip or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="audit_log.csv"'},
    )


# ── Middleware ─────────────────────────────────────────────────────────────

async def audit_middleware(request, call_next):
    """
    FastAPI HTTP middleware — records every API request.
    Attached in src/api/main.py via @app.middleware("http").
    """
    response = await call_next(request)
    try:
        path = request.url.path
        skip_prefixes = ("/docs", "/openapi", "/redoc", "/static", "/api/v1/audit")
        if not any(path.startswith(p) for p in skip_prefixes):
            await record(
                user=request.headers.get("x-user", "anonymous"),
                action=request.method.lower(),
                resource=path,
                detail=f"status={response.status_code}",
                ip=request.client.host if request.client else "",
            )
    except Exception as exc:
        log.debug("audit middleware skipped: %s", exc)
    return response
