"""
Continual-learning API — Enhancement 5 wired into the running app.

Admin-only endpoints to trigger an Elastic Weight Consolidation incremental-learning
round on the trained ActionRecognizer and to inspect past runs. The round itself is
CPU-bound and may take a minute or more, so it is executed on a background daemon thread;
the trigger endpoint returns immediately with a run identifier that the UI can poll.
"""
from __future__ import annotations

import threading
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.api.routes.deps import require_roles
from src.database.models import User
from src.intelligence import continual_learning_service as cls

router = APIRouter(prefix="/api/v1/continual", tags=["continual-learning"])


class CLRunRequest(BaseModel):
    ewc_lambda: float = Field(1000.0, ge=0.0, le=1_000_000.0)
    epochs: int = Field(1, ge=1, le=10)
    max_clips: int = Field(12, ge=2, le=200)


def _launch(run_id: str, params: CLRunRequest, triggered_by: str) -> None:
    thread = threading.Thread(
        target=cls.run_round,
        args=(run_id,),
        kwargs={
            "ewc_lambda": params.ewc_lambda,
            "epochs": params.epochs,
            "max_clips": params.max_clips,
            "triggered_by": triggered_by,
        },
        daemon=True,
    )
    thread.start()


@router.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    body: CLRunRequest | None = None,
    user: User = Depends(require_roles("admin")),
) -> dict:
    """Launch a continual-learning round on a background thread; returns its run id."""
    params = body or CLRunRequest()
    # Reject overlapping runs so concurrent rounds cannot corrupt each other.
    if any(r.get("status") == "running" for r in cls.list_runs()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A continual-learning run is already in progress.",
        )
    run_id = uuid.uuid4().hex[:12]
    _launch(run_id, params, triggered_by=user.email)
    return {"run_id": run_id, "status": "running"}


@router.get("/runs")
async def get_runs(user: User = Depends(require_roles("admin"))) -> list[dict]:
    """List all continual-learning runs, most recent first."""
    return cls.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: User = Depends(require_roles("admin"))) -> dict:
    record = cls.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return record
