"""v1.8: cursos e certificados fora da faculdade (D38–D44)

Revision ID: f2c8e1a7b934
Revises: e7a1c4d9b2f5
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2c8e1a7b934"
down_revision: str | None = "e7a1c4d9b2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = [
    sa.Column("platform", sa.String(100), nullable=True),
    sa.Column("course_type", sa.String(30), nullable=True),
    sa.Column("url", sa.String(500), nullable=True),
    sa.Column("course_status", sa.String(20), nullable=True),
    sa.Column("start_date", sa.Date(), nullable=True),
    sa.Column("target_date", sa.Date(), nullable=True),
    sa.Column("certificate_path", sa.String(500), nullable=True),
    sa.Column("counts_acc", sa.Boolean(), nullable=False, server_default="0"),
    sa.Column("acc_category", sa.String(100), nullable=True),
    sa.Column("notion_page_id", sa.String(64), nullable=True),
    sa.Column("exam_at", sa.DateTime(), nullable=True),
    sa.Column("manual_progress", sa.Integer(), nullable=True),
    sa.Column("finished_on", sa.Date(), nullable=True),
    sa.Column("acc_activity_id", sa.Integer(), nullable=True),
]


def upgrade() -> None:
    # Colunas novas em degree; um curso é uma graduação do tipo "course" (D39)
    with op.batch_alter_table("degree") as batch:
        for col in COLUMNS:
            batch.add_column(col)
        batch.create_foreign_key("fk_degree_acc_activity", "acc_activity", ["acc_activity_id"], ["id"],
                                 ondelete="SET NULL")


def downgrade() -> None:
    with op.batch_alter_table("degree") as batch:
        batch.drop_constraint("fk_degree_acc_activity", type_="foreignkey")
        for col in reversed(COLUMNS):
            batch.drop_column(col.name)
