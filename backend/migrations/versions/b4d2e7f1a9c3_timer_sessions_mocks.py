"""v1.4: sessões do cronômetro, simulados como tipo próprio, página do Notion em prazos

Revision ID: b4d2e7f1a9c3
Revises: 8a3c1d9e4f20
Create Date: 2026-11-12 15:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4d2e7f1a9c3'
down_revision: Union[str, None] = '8a3c1d9e4f20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D24: sessão do cronômetro (Iniciar até Finalizar/Zerar), com pausas e o relógio oculto
    op.create_table(
        'timer_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('pauses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('wall_seconds', sa.Integer(), nullable=True),
        sa.Column('end_reason', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('study_session', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timer_session_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_study_session_timer', 'timer_session', ['timer_session_id'], ['id'],
                                    ondelete='SET NULL')
    with op.batch_alter_table('deadline', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notion_page_id', sa.String(length=64), nullable=True))
    # Simulados da faculdade (cadastrados em 12/11/2026 como "atividade") passam a ter tipo próprio
    op.execute("UPDATE deadline SET kind = 'mock' WHERE kind = 'activity' AND title LIKE 'Simulado %'")


def downgrade() -> None:
    op.execute("UPDATE deadline SET kind = 'activity' WHERE kind = 'mock'")
    with op.batch_alter_table('deadline', schema=None) as batch_op:
        batch_op.drop_column('notion_page_id')
    with op.batch_alter_table('study_session', schema=None) as batch_op:
        batch_op.drop_constraint('fk_study_session_timer', type_='foreignkey')
        batch_op.drop_column('timer_session_id')
    op.drop_table('timer_session')
