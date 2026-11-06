# FORGE-Vision — System Audit & Fix Plan

**Audit Date:** 2026-04-23  
**Auditor:** Multi-agent system review (Backend API, Frontend UI, CV/Security)  
**Status:** In Progress

---

## Overall System Health

| Layer | Status | Notes |
|-------|--------|-------|
| CV Pipeline (MediaPipe + YOLOv8) | ✅ Complete | Real models, wired end-to-end |
| Intelligence / Deviation Detection | ✅ Complete | 6 deviation classes, severity, WHAT+WHY |
| LLM Feedback (6 providers) | ✅ Complete | OpenAI, Groq, Anthropic, Gemini, xAI, Ollama |
| FastAPI — Auth & Account routes | ✅ Complete | JWT + RBAC enforced |
| FastAPI — ALL other routes | ❌ Unauthenticated | analytics, reports, workers, settings, users, sops, audit, session |
| Streamlit — Bearer token passing | ❌ Missing in 17/19 pages | Only account_page.py passes auth headers |
| Docker / Secrets | ❌ Hardcoded credentials | DB password and JWT secret in source |
| Test Coverage — ML / CV | ✅ 454 tests | Thorough |
| Test Coverage — REST session endpoints | ❌ Zero | No session or auth route tests |
| Database Migrations | ❌ Missing | No Alembic configured |
| Audit Logs | ❌ In-memory only | Lost on API restart |

---

## Fix Checklist

### PRIORITY 0 — Critical Security

- [x] **P0.1** — Created/expanded `src/ui/utils.py` with `_headers()`, `_api_base()`, `api_get/post/patch/delete` helpers
- [x] **P0.2** — All 17 Streamlit pages updated to use shared utils (Bearer token passed on every API call)
- [x] **P0.3** — `analytics.py`, `reports.py`, `worker.py` — router-level `Depends(get_current_user)` added
- [x] **P0.4** — `users.py` — `Depends(require_roles("admin"))`; `settings.py` — `Depends(require_roles("admin"))`; `sops.py` POST/DELETE — per-endpoint `Depends(require_roles("admin","trainer"))`; `audit.py` — `Depends(require_roles("admin"))`
- [x] **P0.5** — `docker-compose.yml` DB credentials moved to `${POSTGRES_PASSWORD}` env var; added to `.env`
- [x] **P0.6** — CORS restricted: `allow_methods` and `allow_headers` now explicit lists in `main.py`
- [x] **P2.5** — Startup secret validation added to `main.py` lifespan (rejects dev JWT_SECRET_KEY in production)

**Verified:** Unauthenticated → `{"detail":"Not authenticated"}` on all protected endpoints. Worker token → 200 on analytics, 403 on admin/users. ✅

### PRIORITY 1 — Functional Gaps

- [x] **P1.1** — Added `GET /api/v1/analytics/sessions/{session_id}/deviations` endpoint to `analytics.py`
- [x] **P1.2** — Session History page: replaced JSON dump with structured `st.dataframe()` deviation table
- [x] **P1.3** — My Progress page: Worker ID defaults to `session_state["user"]["id"]`
- [x] **P1.4** — Leaderboard page: Worker ID defaults to `session_state["user"]["id"]`
- [x] **P1.5** — Live Training: load SOPs from API instead of local filesystem
- [x] **P1.6** — Live Training: add WebSocket reconnection (3 retries with backoff)
- [x] **P1.7** — Admin Users page: `_get/_patch/_post` now use shared utils (Bearer token included)
- [x] **P1.8** — Session History + Report Generator CSV exports now pass auth headers

### PRIORITY 2 — Architecture & Reliability

- [x] **P2.1** — Configure Alembic database migrations
- [x] **P2.2** — Add `AuditLog` model + persist audit events to PostgreSQL
- [x] **P2.3** — Email service for password reset (replace stdout print)
- [x] **P2.4** — Add `tests/api/test_session_routes.py` (session endpoint integration tests)

### PRIORITY 3 — UX & Research Enhancements

- [x] **P3.1** — Report Generator: add server-side aggregate endpoint (replace N×M client calls)
- [x] **P3.2** — TTS implementation in Live Training feedback card
- [x] **P3.3** — Add LLM provider/model to `TrainingSessionLog` for reproducibility
- [x] **P3.4** — SOP versioning (auto-bump version on overwrite)

---

## Detailed Fix Instructions

### P0.1 + P0.2 — Shared UI Utility & Bearer Token Auth

**New file:** `src/ui/utils.py`

```python
import streamlit as st
import httpx

def _api_base() -> str:
    return st.session_state.get("api_base_url", "http://localhost:8000")

def _headers() -> dict:
    token = st.session_state.get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}

def api_get(path: str, params: dict | None = None) -> dict | list | None:
    try:
        with httpx.Client(timeout=8.0) as c:
            r = c.get(f"{_api_base()}{path}", params=params or {}, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None

def api_post(path: str, payload: dict) -> dict | None:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.post(f"{_api_base()}{path}", json=payload, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None

def api_patch(path: str, payload: dict) -> dict | None:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.patch(f"{_api_base()}{path}", json=payload, headers=_headers())
            r.raise_for_status()
            return r.json()
    except Exception:
        return None

def api_delete(path: str) -> bool:
    try:
        with httpx.Client(timeout=10.0) as c:
            r = c.delete(f"{_api_base()}{path}", headers=_headers())
            r.raise_for_status()
            return True
    except Exception:
        return False
```

**Pages to update** (replace each page's local `_get/_post/_patch` with `from src.ui.utils import api_get, api_post, api_patch, api_delete`):
1. `dashboard_page.py`
2. `live_training_page.py` (REST calls only; WS uses separate token handling)
3. `analytics_page.py`
4. `session_history_page.py`
5. `worker_profiles_page.py`
6. `leaderboard_page.py`
7. `settings_page.py`
8. `notifications_page.py`
9. `admin_users_page.py`
10. `admin_health_page.py`
11. `admin_audit_page.py`
12. `my_progress_page.py`
13. `report_generator_page.py`
14. `sop_builder_page.py`
15. `sop_library_page.py`
16. `evaluation_page.py`
17. `help_page.py`

---

### P0.3 + P0.4 — Backend Route Authentication

**File:** `src/api/routes/deps.py`  
Add `require_roles()` if not already present:
```python
def require_roles(*roles: str):
    async def _check(current_user: User = Depends(get_current_user)):
        if current_user.role.value not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check
```

**Routes to update:**

| File | Endpoints | Auth to add |
|------|-----------|------------|
| `users.py` | GET/PATCH/POST all | `Depends(require_roles("admin"))` |
| `settings.py` | POST/DELETE/activate | `Depends(require_roles("admin"))` |
| `sops.py` | POST/DELETE | `Depends(require_roles("admin","trainer"))` |
| `analytics.py` | All GET | `Depends(get_current_user)` + role check |
| `reports.py` | All GET | `Depends(get_current_user)` |
| `worker.py` | All | `Depends(get_current_user)` |
| `audit.py` | All | `Depends(require_roles("admin"))` |

---

### P0.5 — Docker Secrets

**File:** `docker-compose.yml`
```yaml
db:
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-forgevision}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    POSTGRES_DB: ${POSTGRES_DB:-forgevision}
```

Add to `.env`: `POSTGRES_PASSWORD=forgevision_dev_pass`

---

### P0.6 — CORS Restriction

**File:** `src/api/main.py`
```python
allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With"],
```

---

### P1.1 — Per-Session Deviation Drill-Down

**Backend (`src/api/routes/analytics.py`)** — add endpoint:
```python
@router.get("/sessions/{session_id}/deviations")
async def get_session_deviations(session_id: str, ...):
    # Query DeviationLog joined with TrainingSessionLog where session_id matches
```

**UI (`src/ui/pages/session_history_page.py`)** — replace JSON dump with `st.dataframe()`.

---

### P1.3 + P1.4 — Auto Worker ID

**`my_progress_page.py` and `leaderboard_page.py`:**
```python
default_id = str(st.session_state.get("user", {}).get("id", ""))
worker_id = st.text_input("Worker ID", value=default_id, ...)
```

---

### P1.5 — Live Training SOP API Loading

**`live_training_page.py`** — replace `_list_sops()` and `_load_sop_for_session()`:
- `_list_sops()` → call `api_get("/api/v1/sops/")`
- `_load_sop_for_session(sop_id)` → call `api_get(f"/api/v1/sops/{sop_id}")` then construct SOP object

---

### P1.6 — WebSocket Reconnection

**`live_training_page.py`** `_ws_reader()` — wrap connect+recv loop in retry loop (3 attempts, exponential backoff).

---

### P2.1 — Alembic Migrations

```bash
pip install alembic
alembic init alembic
# Configure alembic/env.py
alembic revision --autogenerate -m "initial_schema"
alembic upgrade head
```

---

### P2.5 — Startup Secret Validation

**`src/api/main.py`** — add to lifespan:
```python
if settings.ENVIRONMENT == "production":
    if settings.JWT_SECRET_KEY == "dev-secret-change-in-production":
        raise RuntimeError("JWT_SECRET_KEY must be changed before production")
```

---

## Verification

### Security verification (after P0):
```bash
# Should return 401
curl http://localhost:8000/api/v1/analytics/summary

# Should return 403 for non-admin
curl -H "Authorization: Bearer <trainer_token>" http://localhost:8000/api/v1/admin/users/

# Should return 200 for admin
curl -H "Authorization: Bearer <admin_token>" http://localhost:8000/api/v1/admin/users/
```

### Feature verification (after P1):
1. My Progress and Leaderboard auto-load logged-in user's data
2. Session History → click any session → structured deviation table appears
3. Create SOP via Builder → appears in Live Training SOP dropdown (API-driven)
4. Live Training → disconnect WS → reconnects automatically

### Full end-to-end workflow:
1. Admin creates Worker user → Worker logs in
2. Worker starts Live Training session → completes steps → Session Summary renders
3. Supervisor views Session History → drills into deviation log
4. Admin checks Audit Log → all actions recorded and persisted
