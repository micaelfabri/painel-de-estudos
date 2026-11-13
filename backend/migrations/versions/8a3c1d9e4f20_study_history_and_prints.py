"""v1.3: concluído/resultado em provas e prazos, histórico, simulado

Revision ID: 8a3c1d9e4f20
Revises: 5e1f0a2b7c3d
Create Date: 2026-11-12 11:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8a3c1d9e4f20'
down_revision: Union[str, None] = '5e1f0a2b7c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # D14: marcar provas e prazos como feitos; D17: resultado de labs/atividades pelos prints
    with op.batch_alter_table('exam', schema=None) as batch_op:
        batch_op.add_column(sa.Column('done_at', sa.DateTime(), nullable=True))
    with op.batch_alter_table('deadline', schema=None) as batch_op:
        batch_op.add_column(sa.Column('done_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('total_questions', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('first_try_correct', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('wrong_attempts', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('score', sa.Float(), nullable=True))
    # D15/D16: simulado sem tema único, conjunto de origem e tempo do simulado
    with op.batch_alter_table('question_set', schema=None) as batch_op:
        batch_op.alter_column('topic_id', existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column('subject_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_set_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('time_limit_minutes', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_question_set_subject', 'subject', ['subject_id'], ['id'], ondelete='CASCADE')
        batch_op.create_foreign_key('fk_question_set_source', 'question_set', ['source_set_id'], ['id'],
                                    ondelete='SET NULL')
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('topic_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_question_topic', 'topic', ['topic_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint('fk_question_topic', type_='foreignkey')
        batch_op.drop_column('topic_id')
    with op.batch_alter_table('question_set', schema=None) as batch_op:
        batch_op.drop_constraint('fk_question_set_source', type_='foreignkey')
        batch_op.drop_constraint('fk_question_set_subject', type_='foreignkey')
        batch_op.drop_column('time_limit_minutes')
        batch_op.drop_column('source_set_id')
        batch_op.drop_column('subject_id')
        batch_op.alter_column('topic_id', existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table('deadline', schema=None) as batch_op:
        for col in ('score', 'wrong_attempts', 'first_try_correct', 'total_questions', 'done_at'):
            batch_op.drop_column(col)
    with op.batch_alter_table('exam', schema=None) as batch_op:
        batch_op.drop_column('done_at')
