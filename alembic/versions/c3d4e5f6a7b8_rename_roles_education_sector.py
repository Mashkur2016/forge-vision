"""rename_roles_education_sector

Rename 'worker' → 'staff' and 'supervisor' → 'manager' in the userrole enum
to reflect FORGE-Vision's Education Sector focus (University / College / School).

Strategy: cast column to TEXT, drop old enum, create new enum, update data,
re-cast column.  This avoids the PostgreSQL "unsafe use of new enum value"
restriction that occurs when ADD VALUE and UPDATE run in the same transaction.

Revision ID: c3d4e5f6a7b8
Revises: a10176182c5d
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "a10176182c5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Cast column to plain text so we can drop the enum type
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text")
    op.execute("DROP TYPE userrole")

    # 2. Rename old values in the data
    op.execute("UPDATE users SET role = 'staff'   WHERE role = 'worker'")
    op.execute("UPDATE users SET role = 'manager' WHERE role = 'supervisor'")

    # 3. Create the new enum and re-cast the column
    op.execute("CREATE TYPE userrole AS ENUM ('staff', 'trainer', 'manager', 'admin')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users ALTER COLUMN role TYPE text")
    op.execute("DROP TYPE userrole")

    op.execute("UPDATE users SET role = 'worker'     WHERE role = 'staff'")
    op.execute("UPDATE users SET role = 'supervisor' WHERE role = 'manager'")

    op.execute("CREATE TYPE userrole AS ENUM ('worker', 'trainer', 'supervisor', 'admin')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE userrole USING role::userrole"
    )
