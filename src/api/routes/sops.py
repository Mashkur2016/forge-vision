"""
SOP CRUD API Routes.

Reads, creates and deletes SOP YAML/JSON files under data/sops/.

Endpoints:
    GET    /api/v1/sops/           — list all SOPs
    GET    /api/v1/sops/{sop_id}   — full SOP detail
    POST   /api/v1/sops/           — create a new SOP file
    DELETE /api/v1/sops/{sop_id}   — delete a SOP file
"""
from __future__ import annotations

import glob
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.routes.deps import get_current_user, require_roles
from src.simulation.sop_parser import load_sop
from src.simulation.sop_schema import SOP

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/sops", tags=["SOPs"])

# Resolve relative to the project root so Docker and local both work
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SOP_DIR = _PROJECT_ROOT / "data" / "sops"


# ── Helpers ────────────────────────────────────────────────────────────────

def _list_sop_paths() -> list[Path]:
    _SOP_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for ext in ("*.yaml", "*.yml", "*.json"):
        paths.extend(sorted(_SOP_DIR.glob(ext)))
    return paths


def _bump_version_id(sop_id: str) -> str:
    """motor_wiring_v1 → motor_wiring_v2; motor_wiring → motor_wiring_v2"""
    m = re.match(r'^(.+?)_v(\d+)$', sop_id)
    if m:
        return f"{m.group(1)}_v{int(m.group(2)) + 1}"
    return f"{sop_id}_v2"


def _find_sop_path(sop_id: str) -> Path | None:
    for p in _list_sop_paths():
        try:
            sop = load_sop(p)
            if sop.id == sop_id:
                return p
        except Exception:
            continue
    return None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def list_sops() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _list_sop_paths():
        try:
            sop = load_sop(path)
            out.append({
                "id": sop.id,
                "name": sop.name,
                "version": sop.version,
                "category": sop.category,
                "department": sop.department,
                "step_count": sop.step_count,
                "estimated_duration_seconds": sop.estimated_duration_seconds,
                "required_ppe": sop.required_ppe,
                "file": path.name,
            })
        except Exception as exc:
            log.warning("Skipping SOP file %s: %s", path, exc)
    return out


@router.get("/{sop_id}")
async def get_sop(sop_id: str) -> dict[str, Any]:
    path = _find_sop_path(sop_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SOP '{sop_id}' not found")
    try:
        sop = load_sop(path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse SOP: {exc}",
        )
    return sop.model_dump()


@router.post("/", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_roles("admin", "trainer"))])
async def create_sop(body: dict[str, Any]) -> dict[str, Any]:
    """
    Create a new SOP. Body can be either the bare SOP payload or wrapped
    under {"sop": {...}} — both forms are accepted.
    """
    payload = body.get("sop") if isinstance(body.get("sop"), dict) else body

    # Validate via the Pydantic schema
    try:
        sop = SOP.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"SOP validation failed: {exc}",
        )

    # Auto-bump version if a SOP with the same id already exists
    versioned = False
    if _find_sop_path(sop.id) is not None:
        new_id = _bump_version_id(sop.id)
        while _find_sop_path(new_id) is not None:
            new_id = _bump_version_id(new_id)
        sop = sop.model_copy(update={"id": new_id})
        versioned = True

    _SOP_DIR.mkdir(parents=True, exist_ok=True)
    path = _SOP_DIR / f"{sop.id}.yaml"
    yaml_text = yaml.dump({"sop": sop.model_dump()}, allow_unicode=True, sort_keys=False)
    path.write_text(yaml_text, encoding="utf-8")

    log.info("%s SOP %s at %s", "Versioned" if versioned else "Created", sop.id, path)
    return {"ok": True, "id": sop.id, "file": str(path.name), "versioned": versioned}


@router.delete("/{sop_id}", dependencies=[Depends(require_roles("admin", "trainer"))])
async def delete_sop(sop_id: str) -> dict[str, Any]:
    path = _find_sop_path(sop_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"SOP '{sop_id}' not found")
    try:
        os.remove(path)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete SOP file: {exc}",
        )
    log.info("Deleted SOP %s (%s)", sop_id, path)
    return {"ok": True, "id": sop_id}
