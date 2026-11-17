"""v1.10 (D53): tarefa guarda os ids de todos os seus temas (checklist_item.topic_ids)

Preenche as tarefas de tema que já existem com os temas que o texto cita hoje (ou só o primeiro tema, quando o
texto não bate mais, por exemplo depois de renomear). Só acrescenta a coluna; nada é apagado.

Revision ID: c7e3a1d5b820
Revises: b4d9e2f7a613
"""

import json
import re

import sqlalchemy as sa
from alembic import op

revision = "c7e3a1d5b820"
down_revision = "b4d9e2f7a613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("checklist_item") as batch:
        batch.add_column(sa.Column("topic_ids", sa.JSON(), nullable=True))
    bind = op.get_bind()
    items = bind.execute(sa.text("SELECT id, label, topic_id FROM checklist_item WHERE topic_id IS NOT NULL")).all()
    for item_id, label, topic_id in items:
        subject = bind.execute(sa.text("SELECT subject_id FROM topic WHERE id = :t"), {"t": topic_id}).scalar()
        ids = [topic_id]
        if subject is not None and label.startswith(("Estudar ", "Concluir ")):
            text = label.split(" · ")[0]
            rows = bind.execute(sa.text("SELECT id, title FROM topic WHERE subject_id = :s ORDER BY position, id"),
                                {"s": subject}).all()
            found = [i for i, title in rows if re.search(rf"(?<![\w]){re.escape(title)}(?![\w])", text)]
            ids = found or ids
        bind.execute(sa.text("UPDATE checklist_item SET topic_ids = :v WHERE id = :i"),
                     {"v": json.dumps(ids), "i": item_id})


def downgrade() -> None:
    with op.batch_alter_table("checklist_item") as batch:
        batch.drop_column("topic_ids")
