"""
Synthetic Database Seeder — Phase 5 Simulation Evaluation Track.

Materialises the in-memory participants from :class:`SyntheticParticipantGenerator`
into operational database rows (``users``, ``worker_profiles``,
``training_session_logs``, ``deviation_logs``) so that the dashboard, analytics,
leaderboard, session-history and competency pages have realistic data to render
WITHOUT requiring the ethics-gated recruitment of real participants.

This is the *simulation track* — it has no ethics dependency.  Real-participant
work (TODOList tasks 5.1–5.5) remains separate and pending ethics approval.

Rules.md compliance
-------------------
* §3.1  ALL seeded data is explicitly labelled SYNTHETIC and can never be mistaken
        for real participant data:
            - ``users.department == "SYNTHETIC"``
            - ``users.email`` ends with ``@synthetic.forge.local``
        Real accounts (e.g. the admin user) are NEVER touched by this script.
* §1.5  Reproducible: a fixed seed drives every random draw.
* §1.6  Every DeviationLog row carries a populated WHAT and WHY explanation.

Usage
-----
    # Study scale (64 workers per group = 256 staff + trainers/managers)
    python -m src.evaluation.seed_simulation_data

    # Small demo scale
    python -m src.evaluation.seed_simulation_data --demo

    # Deploy hook — only seed when the database is empty (idempotent first boot)
    python -m src.evaluation.seed_simulation_data --if-empty

    # Remove all synthetic rows and exit (real data untouched)
    python -m src.evaluation.seed_simulation_data --wipe-only

The seeder targets whatever ``DATABASE_URL`` the application is configured with
(SQLite locally, PostgreSQL on a host), so a single command serves every
environment.
"""
from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
from passlib.context import CryptContext
from sqlalchemy import delete, func, select

from src.database.database import AsyncSessionLocal, create_tables
from src.database.models import (
    DeviationLog,
    SkillLevel,
    TrainingSessionLog,
    User,
    UserRole,
    WorkerProfile,
)
from src.evaluation.synthetic_participants import (
    ParticipantRecord,
    SyntheticParticipantGenerator,
)
from src.simulation.sop_parser import load_all_sops
from src.simulation.sop_schema import SOP

# ── Synthetic markers (Rules.md §3.1) ────────────────────────────────────────
SYNTHETIC_EMAIL_DOMAIN = "synthetic.forge.local"
SYNTHETIC_DEPARTMENT = "SYNTHETIC"

# Worker study groups that become real User rows (hybrid_posthoc is an H3-only
# in-memory comparison group and is intentionally NOT materialised here).
_WORKER_GROUPS = ("control", "sim_only", "realtime_only", "hybrid")

# The four-week window the seeded sessions are spread across (most recent first).
_HISTORY_WEEKS = 8

# Deviation classes that can appear in a DeviationLog (CORRECT is never a log row).
# Weighted so safety-critical (HIGH) events stay realistically rare.
_DEVIATION_CLASSES = ["MISSING_STEP", "WRONG_ORDER", "INCORRECT_EXECUTION", "MISSING_PPE", "UNSAFE_POSTURE"]
_DEVIATION_WEIGHTS = [0.34, 0.26, 0.22, 0.10, 0.08]

# Affective-state samples (Enhancement 7). Stored as `emotion_*` DeviationLog rows
# (excluded from deviation analytics, surfaced in the Emotion & Stress tab).
# Per-group mix tells the H1/H2 story: the hybrid arm is calmer/more focused; the
# control arm shows more stress/fatigue.
_EMOTION_STATES = ["focused", "neutral", "stressed", "fatigued"]
_EMOTION_WEIGHTS_BY_GROUP = {
    "control":       [0.25, 0.25, 0.30, 0.20],
    "sim_only":      [0.40, 0.30, 0.18, 0.12],
    "realtime_only": [0.50, 0.30, 0.12, 0.08],
    "hybrid":        [0.62, 0.28, 0.06, 0.04],
}
_EMOTIONS_PER_SESSION = 3

# Realistic operational departments for the Bias Audit. Synthetic identity is
# carried by the @synthetic.forge.local email (used by the wipe), so the
# department field is free to hold these. ONE department is modelled with a
# higher error rate to demonstrate the fairness audit detecting a disparity.
_DEPARTMENTS = ["Assembly", "Packaging", "Welding", "Quality Assurance", "Maintenance"]
_BIASED_DEPARTMENT = "Welding"
_BIAS_DEV_MULTIPLIER = 1.5

# LLM provider/model pairs stamped across sessions (pre-seeds task 5.7 comparison).
_LLM_STAMPS = [
    ("groq", "llama-3.1-8b-instant"),
    ("gemini", "gemini-1.5-flash"),
    ("ollama", "llama3.1:8b"),
]

_FIRST_NAMES = [
    "Aisha", "Ben", "Chloe", "Dev", "Elena", "Femi", "Grace", "Hassan", "Isla",
    "Jamal", "Kira", "Liam", "Mei", "Noah", "Omar", "Priya", "Quinn", "Rosa",
    "Sam", "Tariq", "Uma", "Victor", "Wei", "Xena", "Yusuf", "Zoe",
]
_LAST_NAMES = [
    "Ahmed", "Brown", "Chen", "Diaz", "Evans", "Fischer", "Gupta", "Hughes",
    "Ivanov", "Jones", "Khan", "Lopez", "Mensah", "Nguyen", "Owusu", "Patel",
    "Robinson", "Singh", "Taylor", "Ueda", "Vargas", "Wright", "Yilmaz", "Zhang",
]

# Constructive, non-punitive feedback templates (Rules.md §2.2).
# Corrective-feedback templates now live in src/intelligence/feedback_templates.py
# (shared with the feedback API + the Template-vs-Groq demo).
from src.intelligence.feedback_templates import get_template_feedback

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _severity_for(deviation_class: str, safety_critical: bool) -> str:
    """Mirror SOPDetector._classify_severity so seeded severities match live data."""
    if deviation_class in ("MISSING_PPE", "UNSAFE_POSTURE"):
        return "high"
    if deviation_class == "MISSING_STEP":
        return "high" if safety_critical else "medium"
    if deviation_class == "INCORRECT_EXECUTION":
        return "high" if safety_critical else "medium"
    if deviation_class == "WRONG_ORDER":
        return "medium"
    return "medium"


def _explain(deviation_class: str, step_name: str, step_id: int, sop_name: str) -> tuple[str, str]:
    """Standalone WHAT/WHY generator mirroring SOPDetector._explain (Rules.md §1.6)."""
    table = {
        "MISSING_STEP": (
            f"Step {step_id} ({step_name}) appears to have been skipped.",
            f"SOP requires step {step_id} before proceeding. Skipping '{step_name}' may compromise procedure integrity.",
        ),
        "WRONG_ORDER": (
            f"Steps performed out of order near step {step_id} ({step_name}).",
            f"SOP '{sop_name}' defines a strict step sequence. Step {step_id} must follow its predecessors as defined.",
        ),
        "INCORRECT_EXECUTION": (
            f"Step {step_id} ({step_name}) was not executed correctly.",
            f"The observed actions do not match the required execution for '{step_name}' as defined in the SOP.",
        ),
        "MISSING_PPE": (
            "Required personal protective equipment not detected.",
            f"SOP '{sop_name}' mandates PPE throughout the procedure.",
        ),
        "UNSAFE_POSTURE": (
            "Unsafe body posture or movement detected.",
            "Worker posture or movement pattern indicates a potential safety risk. Safe posture must be maintained per SOP guidelines.",
        ),
    }
    return table.get(deviation_class, (f"Deviation detected: {deviation_class}", "Action sequence does not match SOP."))


def _skill_from_accuracy(accuracy: float) -> SkillLevel:
    if accuracy >= 0.90:
        return SkillLevel.proficient
    if accuracy >= 0.80:
        return SkillLevel.competent
    if accuracy >= 0.70:
        return SkillLevel.developing
    return SkillLevel.beginner


# ── Wipe ──────────────────────────────────────────────────────────────────────

async def wipe_synthetic(session) -> dict[str, int]:
    """
    Delete every synthetic row, leaving real accounts and data untouched.

    Deletion is explicit and ordered (deviations → sessions → profiles → users)
    rather than relying on ON DELETE CASCADE, because SQLite does not enforce
    foreign keys by default and ``training_session_logs.worker_id`` is SET NULL,
    not CASCADE.
    """
    result = await session.execute(
        select(User.id).where(User.email.like(f"%@{SYNTHETIC_EMAIL_DOMAIN}"))
    )
    synthetic_ids = [row[0] for row in result.all()]
    counts = {"users": 0, "worker_profiles": 0, "training_session_logs": 0, "deviation_logs": 0}
    if not synthetic_ids:
        return counts

    sess_result = await session.execute(
        select(TrainingSessionLog.id).where(TrainingSessionLog.worker_id.in_(synthetic_ids))
    )
    session_ids = [row[0] for row in sess_result.all()]

    if session_ids:
        d = await session.execute(
            delete(DeviationLog).where(DeviationLog.session_log_id.in_(session_ids))
        )
        counts["deviation_logs"] = d.rowcount or 0
        s = await session.execute(
            delete(TrainingSessionLog).where(TrainingSessionLog.id.in_(session_ids))
        )
        counts["training_session_logs"] = s.rowcount or 0

    p = await session.execute(
        delete(WorkerProfile).where(WorkerProfile.user_id.in_(synthetic_ids))
    )
    counts["worker_profiles"] = p.rowcount or 0
    u = await session.execute(delete(User).where(User.id.in_(synthetic_ids)))
    counts["users"] = u.rowcount or 0

    await session.commit()
    return counts


# ── Seed ────────────────────────────────────────────────────────────────────────

def _make_user(rng, group: str, idx: int, role: UserRole, password_hash: str,
               department: str = SYNTHETIC_DEPARTMENT) -> User:
    first = _FIRST_NAMES[rng.integers(0, len(_FIRST_NAMES))]
    last = _LAST_NAMES[rng.integers(0, len(_LAST_NAMES))]
    created = datetime.now(timezone.utc) - timedelta(days=int(rng.integers(60, 400)))
    return User(
        email=f"{group}.{role.value}.{idx:03d}@{SYNTHETIC_EMAIL_DOMAIN}",
        first_name=first,
        last_name=last,
        password_hash=password_hash,
        role=role,
        department=department,
        is_active=True,
        gdpr_consent=True,
        consent_given_at=created,
        created_at=created,
        updated_at=created,
    )


def _build_sessions_for_worker(
    rng,
    record: ParticipantRecord,
    sops: list[SOP],
    primary_sop: SOP,
    dev_multiplier: float = 1.0,
) -> tuple[list[TrainingSessionLog], list[list[DeviationLog]], dict]:
    """
    Build a learning-curve sequence of sessions (+ their deviation rows) for one
    worker.  Returns (sessions, deviations_per_session, profile_aggregates).

    Deviation counts and completion times start high and decline toward the
    participant's competent baseline; accuracy ramps toward final_accuracy.
    """
    n_sessions = max(1, record.sessions_to_competency)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(weeks=_HISTORY_WEEKS)
    span = (now - window_start).total_seconds()

    sessions: list[TrainingSessionLog] = []
    deviations: list[list[DeviationLog]] = []

    total_dev = 0
    total_high = 0
    competency_reached_at: datetime | None = None
    sessions_to_competency_est: int | None = None
    last_accuracy = 0.0

    start_acc = max(0.40, record.final_accuracy - 0.25)

    for k in range(n_sessions):
        progress = k / (n_sessions - 1) if n_sessions > 1 else 1.0

        # Sessions are chronological across the history window.
        offset = span * (k + 0.5) / n_sessions
        jitter = float(rng.normal(0, span / (n_sessions * 6)))
        started_at = window_start + timedelta(seconds=max(0.0, offset + jitter))

        # Learning curve: deviation multiplier falls 1.9 -> 1.0 over the sequence.
        dev_mult = 1.9 + (1.0 - 1.9) * progress
        dev_mean = record.errors_per_task * dev_mult * dev_multiplier
        dev_count = max(0, int(round(float(rng.normal(dev_mean, 0.8)))))

        # Completion time falls toward the participant's baseline.
        time_mult = 1.4 + (1.0 - 1.4) * progress
        completion_min = float(np.clip(rng.normal(record.completion_time_min * time_mult, 1.2), 2.0, 60.0))
        duration_seconds = completion_min * 60.0

        accuracy = float(np.clip(start_acc + (record.final_accuracy - start_acc) * progress + rng.normal(0, 0.03), 0.0, 1.0))
        last_accuracy = accuracy

        ended_at = started_at + timedelta(seconds=duration_seconds)
        fps = float(np.clip(rng.normal(18.0, 3.0), 8.0, 30.0))
        total_frames = int(duration_seconds * fps)
        latency_p95 = float(np.clip(rng.normal(1150.0, 350.0), 300.0, 3000.0))

        # ~80% primary SOP, ~20% a secondary SOP for variety.
        if len(sops) > 1 and rng.random() < 0.20:
            sop = sops[int(rng.integers(0, len(sops)))]
        else:
            sop = primary_sop

        provider, model = _LLM_STAMPS[int(rng.integers(0, len(_LLM_STAMPS)))]

        session_log = TrainingSessionLog(
            session_id=str(uuid.uuid4()),
            sop_id=sop.id,
            sop_name=sop.name,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=duration_seconds,
            total_frames=total_frames,
            actual_fps=round(fps, 2),
            deviation_count=dev_count,
            high_severity_count=0,  # set below once events are built
            latency_p95_ms=round(latency_p95, 1),
            latency_target_met=latency_p95 <= 2000.0,
            llm_provider=provider,
            llm_model=model,
            created_at=ended_at,
        )

        session_devs: list[DeviationLog] = []
        high_in_session = 0
        for _ in range(dev_count):
            dclass = str(rng.choice(_DEVIATION_CLASSES, p=_DEVIATION_WEIGHTS))
            step = sop.steps[int(rng.integers(0, len(sop.steps)))]
            severity = _severity_for(dclass, step.safety_critical)
            if severity == "high":
                high_in_session += 1
            what, why = _explain(dclass, step.name, step.id, sop.name)
            event_ts = started_at.timestamp() + float(rng.uniform(0, duration_seconds))
            session_devs.append(
                DeviationLog(
                    event_timestamp=event_ts,
                    deviation_class=dclass,
                    severity=severity,
                    expected_step_name=step.name,
                    model_confidence=round(float(np.clip(rng.normal(0.82, 0.08), 0.6, 0.99)), 3),
                    what=what,
                    why=why,
                    feedback_text=get_template_feedback(dclass, step.name),
                    created_at=ended_at,
                )
            )

        session_log.high_severity_count = high_in_session
        total_dev += dev_count
        total_high += high_in_session

        # Affective-state samples (added AFTER the deviation counts so they never
        # inflate deviation_count / high_severity_count). severity="low".
        ew = _EMOTION_WEIGHTS_BY_GROUP.get(record.group, _EMOTION_WEIGHTS_BY_GROUP["control"])
        for _ in range(_EMOTIONS_PER_SESSION):
            state = str(rng.choice(_EMOTION_STATES, p=ew))
            ets = started_at.timestamp() + float(rng.uniform(0, duration_seconds))
            session_devs.append(
                DeviationLog(
                    event_timestamp=ets,
                    deviation_class=f"emotion_{state}",
                    severity="low",
                    expected_step_name="",
                    model_confidence=round(float(np.clip(rng.normal(0.7, 0.1), 0.4, 0.95)), 3),
                    what=f"Affective state: {state}",
                    why="MediaPipe FaceMesh affective estimate (Enhancement 7).",
                    created_at=ended_at,
                )
            )

        # First session at/above the competent accuracy threshold marks competency.
        if competency_reached_at is None and accuracy >= 0.80:
            competency_reached_at = ended_at
            sessions_to_competency_est = k + 1

        sessions.append(session_log)
        deviations.append(session_devs)

    last_session_at = sessions[-1].ended_at if sessions else None
    aggregates = {
        "total_sessions": len(sessions),
        "total_deviations": total_dev,
        "total_high_severity": total_high,
        "last_session_at": last_session_at,
        "skill_level": _skill_from_accuracy(last_accuracy),
        "sessions_to_competency_est": sessions_to_competency_est or record.sessions_to_competency,
        "competency_reached_at": competency_reached_at,
    }
    return sessions, deviations, aggregates


async def seed(
    session,
    per_group: int,
    seed_value: int,
    n_trainers: int = 2,
    n_managers: int = 1,
) -> dict[str, int]:
    """Generate and persist the full synthetic dataset.  Assumes a clean slate."""
    rng = np.random.default_rng(seed_value)
    generator = SyntheticParticipantGenerator(seed=seed_value)
    password_hash = _pwd_context.hash("SyntheticDemo123!")

    sops_map = load_all_sops("data/sops")
    sops = sorted(sops_map.values(), key=lambda s: s.id)
    if not sops:
        raise RuntimeError("No SOPs found in data/sops — cannot seed sessions.")

    totals = {"users": 0, "worker_profiles": 0, "training_session_logs": 0, "deviation_logs": 0}

    # ── Staff workers (the four study groups) ──────────────────────────────
    sop_cursor = 0
    for group in _WORKER_GROUPS:
        records = generator.generate_group(group, per_group)

        # Persist this group's users first so they receive primary keys.
        users: list[User] = []
        for i, _record in enumerate(records, start=1):
            dept = _DEPARTMENTS[(i - 1) % len(_DEPARTMENTS)]
            users.append(_make_user(rng, group, i, UserRole.staff, password_hash, dept))
        session.add_all(users)
        await session.flush()
        totals["users"] += len(users)

        for user, record in zip(users, records):
            primary_sop = sops[sop_cursor % len(sops)]
            sop_cursor += 1

            dev_mult = _BIAS_DEV_MULTIPLIER if user.department == _BIASED_DEPARTMENT else 1.0
            sessions, devs_per_session, agg = _build_sessions_for_worker(
                rng, record, sops, primary_sop, dev_multiplier=dev_mult
            )

            session.add(WorkerProfile(
                user_id=user.id,
                skill_level=agg["skill_level"],
                department=user.department,
                employee_id=f"SYN-{user.id:05d}",
                total_sessions=agg["total_sessions"],
                total_deviations=agg["total_deviations"],
                total_high_severity=agg["total_high_severity"],
                last_session_at=agg["last_session_at"],
                sessions_to_competency_est=agg["sessions_to_competency_est"],
                competency_reached_at=agg["competency_reached_at"],
                trainer_notes="[SYNTHETIC] Generated for Phase 5 simulation evaluation track.",
            ))
            totals["worker_profiles"] += 1

            for session_log in sessions:
                session_log.worker_id = user.id
            session.add_all(sessions)
            await session.flush()  # populate session_log.id for deviation FK
            totals["training_session_logs"] += len(sessions)

            for session_log, session_devs in zip(sessions, devs_per_session):
                for dev in session_devs:
                    dev.session_log_id = session_log.id
                session.add_all(session_devs)
                totals["deviation_logs"] += len(session_devs)

        # Commit per group to bound the unit of work.
        await session.commit()

    # ── Trainers and managers (accounts only — for role-filtered views) ────
    role_users: list[User] = []
    for i in range(1, n_trainers + 1):
        role_users.append(_make_user(rng, "staffroom", i, UserRole.trainer, password_hash))
    for i in range(1, n_managers + 1):
        role_users.append(_make_user(rng, "staffroom", i, UserRole.manager, password_hash))
    session.add_all(role_users)
    await session.commit()
    totals["users"] += len(role_users)

    return totals


# ── Orchestration ──────────────────────────────────────────────────────────────

async def _database_has_sessions(session) -> bool:
    result = await session.execute(select(func.count()).select_from(TrainingSessionLog))
    return (result.scalar() or 0) > 0


async def run(per_group: int, seed_value: int, if_empty: bool, wipe_only: bool) -> None:
    await create_tables()
    async with AsyncSessionLocal() as session:
        if if_empty and await _database_has_sessions(session):
            print("[seed] --if-empty: training sessions already exist — skipping.")
            return

        print(f"[seed] SYNTHETIC data seeder (seed={seed_value}) — Rules.md §3.1 labelled.")
        wiped = await wipe_synthetic(session)
        if any(wiped.values()):
            print(f"[seed] Removed prior synthetic rows: {wiped}")

        if wipe_only:
            print("[seed] --wipe-only: done.")
            return

        totals = await seed(session, per_group=per_group, seed_value=seed_value)
        print(f"[seed] Done. Inserted: {totals}")
        print(f"[seed] All synthetic users identified by @{SYNTHETIC_EMAIL_DOMAIN} email "
              f"(department field holds realistic operational units for the bias audit).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic FORGE-Vision training data (labelled SYNTHETIC).")
    parser.add_argument("--per-group", type=int, default=64,
                        help="Synthetic staff workers per study group (x4 groups). Default 64 (study scale).")
    parser.add_argument("--demo", action="store_true",
                        help="Shortcut for --per-group 5 (small demo dataset).")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default 42).")
    parser.add_argument("--if-empty", action="store_true",
                        help="Only seed if no training sessions exist (deploy/first-boot hook).")
    parser.add_argument("--wipe-only", action="store_true",
                        help="Delete all synthetic rows and exit (real data untouched).")
    args = parser.parse_args()

    per_group = 5 if args.demo else args.per_group
    asyncio.run(run(per_group=per_group, seed_value=args.seed,
                    if_empty=args.if_empty, wipe_only=args.wipe_only))


if __name__ == "__main__":
    main()
