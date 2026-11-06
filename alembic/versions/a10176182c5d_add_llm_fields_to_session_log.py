"""add_llm_fields_to_session_log

Revision ID: a10176182c5d
Revises: 24283746806e
Create Date: 2026-04-23 14:23:57.975815

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a10176182c5d'
down_revision: Union[str, Sequence[str], None] = '24283746806e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('training_session_logs', sa.Column('llm_provider', sa.String(length=50), nullable=True))
    op.add_column('training_session_logs', sa.Column('llm_model', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('training_session_logs', 'llm_model')
    op.drop_column('training_session_logs', 'llm_provider')
