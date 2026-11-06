"""
SQLAlchemy ORM models for FORGE-Vision database.

Phase 0: User, LLMSettings
Phase 4: WorkerProfile, TrainingSessionLog, DeviationLog
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func


def _now() -> datetime:
    """Python-side timestamp — avoids server-side func.now() round-trips in async SQLAlchemy."""
    return datetime.now(timezone.utc)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.database import Base


class UserRole(enum.Enum):
    staff = "staff"
    trainer = "trainer"
    manager = "manager"
    admin = "admin"


class User(Base):
    """
    Application user.
    Passwords stored as bcrypt hashes — never plain text.
    MFA TOTP secrets stored Fernet-encrypted (same key as API keys).
    Password reset tokens stored as SHA-256 hashes — never plain text.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.staff,
    )
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # MFA (TOTP — for admin and supervisor roles)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet-encrypted

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # GDPR
    gdpr_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Password reset (token stored as SHA-256 hash, expires after 30 min)
    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"


class LLMSettings(Base):
    """
    Stores the active LLM configuration.
    Only one row is active at a time (single-row upsert pattern).
    API keys are stored Fernet-encrypted — never in plain text.
    """
    __tablename__ = "llm_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Provider identifier: openai | groq | anthropic | gemini | ollama
    provider: Mapped[str] = mapped_column(String(50), nullable=False)

    # Model name, e.g. "gpt-4o-mini", "llama3.1:8b"
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Fernet-encrypted API key — NULL for local Ollama
    api_key_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Base URL for local Ollama, e.g. "http://localhost:11434"
    # NULL for all external providers
    ollama_base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Only one row should have is_active=True at any time
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Set to True only after a successful /settings/test call
    tested_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<LLMSettings provider={self.provider!r} model={self.model_name!r} active={self.is_active}>"


# ── Phase 4: Worker Profile ────────────────────────────────────────────────

class SkillLevel(enum.Enum):
    beginner = "beginner"
    developing = "developing"
    competent = "competent"
    proficient = "proficient"


class WorkerProfile(Base):
    """
    Extended profile for a worker, linked one-to-one with User.

    Stores aggregate performance stats (denormalised for fast dashboard queries)
    and trainer notes. Updated whenever a training session completes.

    Phase 4 — Task 4.3.
    """
    __tablename__ = "worker_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    skill_level: Mapped[SkillLevel] = mapped_column(
        Enum(SkillLevel, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=SkillLevel.beginner,
    )
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    employee_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Denormalised session stats — updated on session completion
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_deviations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_high_severity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_session_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Competency tracking (Enhancement 6)
    sessions_to_competency_est: Mapped[int | None] = mapped_column(Integer, nullable=True)
    competency_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Trainer notes (free text — GDPR: processed only for training purposes)
    trainer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=_now,
        onupdate=_now,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<WorkerProfile user_id={self.user_id} skill={self.skill_level.value}>"


# ── Phase 4: Training Session Log ─────────────────────────────────────────

class TrainingSessionLog(Base):
    """
    Persistent record of a completed real-time training session.

    Created by the session API (src/api/routes/session.py) when a session
    is stopped.  Related DeviationLog rows record individual events.

    Phase 4 — Task 4.2.
    Rules.md §2: Only aggregate stats and anonymised event data are stored.
    Frames are never persisted (processed in memory only per Phase 3 GDPR rule).
    """
    __tablename__ = "training_session_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Runtime session ID from TrainingSession (8-char UUID prefix)
    session_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)

    # Worker (nullable: sessions can be anonymous)
    worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # SOP details
    sop_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sop_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    # Performance metrics
    total_frames: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actual_fps: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    deviation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_severity_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latency_p95_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_target_met: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # LLM audit trail — which provider/model generated feedback (academic reproducibility)
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    deviations: Mapped[list["DeviationLog"]] = relationship(
        "DeviationLog",
        back_populates="session_log",
        cascade="all, delete-orphan",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TrainingSessionLog id={self.id} session={self.session_id!r} "
            f"sop={self.sop_id!r} deviations={self.deviation_count}>"
        )


# ── Phase 4: Deviation Log ─────────────────────────────────────────────────

class DeviationLog(Base):
    """
    Individual deviation event recorded during a training session.

    One row per SOPDeviationEvent emitted by the SOPDetector.
    Includes the LLM feedback text generated in response.

    Phase 4 — Task 4.2.
    Rules.md §1.6: WHAT + WHY always populated (from SOPDeviationEvent).
    """
    __tablename__ = "deviation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("training_session_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Event timing (Unix timestamp from SOPDeviationEvent.timestamp)
    event_timestamp: Mapped[float] = mapped_column(Float, nullable=False)

    # Deviation classification
    deviation_class: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)

    # Step context
    expected_step_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    model_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Explainability (Rules.md §1.6)
    what: Mapped[str] = mapped_column(Text, nullable=False, default="")
    why: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # LLM corrective feedback (nullable: only present when LLM was triggered)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    session_log: Mapped["TrainingSessionLog"] = relationship(
        "TrainingSessionLog", back_populates="deviations"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<DeviationLog id={self.id} class={self.deviation_class!r} "
            f"severity={self.severity!r}>"
        )


# ── Audit Log ──────────────────────────────────────────────────────────────

class AuditLog(Base):
    """
    Persistent audit trail for all admin / data-changing actions.

    Replaces the previous in-memory list in audit.py.
    Survives API restarts; queryable and exportable via the audit endpoints.
    """
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), nullable=False, index=True
    )
    user: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource: Mapped[str] = mapped_column(String(200), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} user={self.user!r} action={self.action!r}>"
