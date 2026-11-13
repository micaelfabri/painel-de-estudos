"""v1.6: cards de estudo (D32–D37)

Revision ID: e7a1c4d9b2f5
Revises: d6f3a8b2c1e4
Create Date: 2026-11-12 19:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e7a1c4d9b2f5'
down_revision: str | None = 'd6f3a8b2c1e4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'card',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('mode', sa.String(length=10), nullable=False),
        sa.Column('front', sa.Text(), nullable=False),
        sa.Column('back', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('correct_index', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=10), nullable=False),
        sa.Column('mistake_id', sa.Integer(), nullable=True),
        sa.Column('source_label', sa.String(length=300), nullable=True),
        sa.Column('chosen_text', sa.Text(), nullable=True),
        sa.Column('video_minute', sa.String(length=10), nullable=True),
        sa.Column('step', sa.Integer(), nullable=False),
        sa.Column('next_review', sa.Date(), nullable=False),
        sa.Column('answer_streak', sa.Integer(), nullable=False),
        sa.Column('day_card_on', sa.Date(), nullable=True),
        sa.Column('prompt_version', sa.String(length=80), nullable=True),
        sa.Column('notion_synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['topic_id'], ['topic.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['mistake_id'], ['mistake.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_card_next_review', 'card', ['next_review'])
    op.create_table(
        'card_review',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('mode', sa.String(length=10), nullable=False),
        sa.Column('knew', sa.Boolean(), nullable=False),
        sa.Column('chosen_index', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['card.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('card_review')
    op.drop_index('ix_card_next_review', table_name='card')
    op.drop_table('card')
