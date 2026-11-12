"""notion sync mark on question sets

Revision ID: 5e1f0a2b7c3d
Revises: 0047ca8c16fc
Create Date: 2026-11-10 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5e1f0a2b7c3d'
down_revision: Union[str, None] = '0047ca8c16fc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Quando o resultado do conjunto foi gravado na página do tema no Notion (F5)
    with op.batch_alter_table('question_set', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notion_synced_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('question_set', schema=None) as batch_op:
        batch_op.drop_column('notion_synced_at')
