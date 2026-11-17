"""v1.8.3 (D49): tarefa passada para outro dia deixa rastro (checklist_item.carried_to)

Também corrige o passado: cada tarefa não feita que tem a mesma tarefa num dia depois passa a apontar para
o próximo desses dias. Antes de mexer, salva uma cópia do banco em data/backups. Nada é apagado.

Revision ID: b4d9e2f7a613
Revises: f2c8e1a7b934
"""

import sqlite3
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "b4d9e2f7a613"
down_revision = "f2c8e1a7b934"
branch_labels = None
depends_on = None


def _backup(bind) -> None:
    """Cópia inteira do banco antes da correção (API de backup do SQLite, segura com o banco aberto)."""
    db = bind.engine.url.database
    if bind.dialect.name != "sqlite" or not db or db == ":memory:" or not Path(db).exists():
        return
    dest_dir = Path(db).parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{Path(db).stem}-antes-v1.8.3.db"
    if dest.exists():
        return
    src = sqlite3.connect(db)
    out = sqlite3.connect(dest)
    try:
        src.backup(out)
    finally:
        out.close()
        src.close()


def upgrade() -> None:
    bind = op.get_bind()
    _backup(bind)
    with op.batch_alter_table("checklist_item") as batch:
        batch.add_column(sa.Column("carried_to", sa.Date(), nullable=True))

    # Passado: não feita + mesma tarefa num dia depois → aponta para o próximo desses dias
    rows = bind.execute(sa.text("SELECT id, day, label, done FROM checklist_item ORDER BY day, id")).fetchall()
    days_by_label: dict[str, list[str]] = {}
    for _id, day, label, _done in rows:
        days_by_label.setdefault(label, []).append(str(day))
    for item_id, day, label, done in rows:
        if done:
            continue
        later = sorted(d for d in days_by_label[label] if d > str(day))
        if later:
            bind.execute(sa.text("UPDATE checklist_item SET carried_to = :d WHERE id = :i"),
                         {"d": later[0], "i": item_id})


def downgrade() -> None:
    with op.batch_alter_table("checklist_item") as batch:
        batch.drop_column("carried_to")
