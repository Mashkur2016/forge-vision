"""initial_schema

Revision ID: 24283746806e
Revises:
Create Date: 2026-04-23

Complete initial schema for FORGE-Vision.
Tables: users, llm_settings, worker_profiles, training_session_logs, deviation_logs, audit_logs.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "24283746806e"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("worker", "trainer", "supervisor", "admin", name="userrole"), nullable=False),
        sa.Column("department", sa.String(150), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("mfa_secret_enc", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("gdpr_consent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_reset_token_hash", sa.String(64), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("api_key_enc", sa.Text(), nullable=True),
        sa.Column("ollama_base_url", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tested_ok", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "worker_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "skill_level",
            sa.Enum("beginner", "developing", "competent", "proficient", name="skilllevel"),
            nullable=False,
        ),
        sa.Column("department", sa.String(150), nullable=True),
        sa.Column("employee_id", sa.String(50), nullable=True),
        sa.Column("total_sessions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_deviations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_high_severity", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_session_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sessions_to_competency_est", sa.Integer(), nullable=True),
        sa.Column("competency_reached_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trainer_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "training_session_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=True),
        sa.Column("sop_id", sa.String(100), nullable=False),
        sa.Column("sop_name", sa.String(200), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("total_frames", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("actual_fps", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("deviation_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("high_severity_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_p95_ms", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("latency_target_met", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["worker_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_training_session_logs_session_id", "training_session_logs", ["session_id"], unique=True)
    op.create_index("ix_training_session_logs_worker_id", "training_session_logs", ["worker_id"], unique=False)

    op.create_table(
        "deviation_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_log_id", sa.Integer(), nullable=False),
        sa.Column("event_timestamp", sa.Float(), nullable=False),
        sa.Column("deviation_class", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("expected_step_name", sa.String(200), nullable=False, server_default=sa.text("''")),
        sa.Column("model_confidence", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("what", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("why", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("feedback_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_log_id"], ["training_session_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deviation_logs_session_log_id", "deviation_logs", ["session_log_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("user", sa.String(255), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False)
    op.create_index("ix_audit_logs_user", "audit_logs", ["user"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_logs_user", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_deviation_logs_session_log_id", table_name="deviation_logs")
    op.drop_table("deviation_logs")
    op.drop_index("ix_training_session_logs_worker_id", table_name="training_session_logs")
    op.drop_index("ix_training_session_logs_session_id", table_name="training_session_logs")
    op.drop_table("training_session_logs")
    op.drop_table("worker_profiles")
    op.drop_table("llm_settings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS skilllevel")
