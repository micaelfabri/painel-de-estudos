"""v1.5: ciclo dos erros, questão de origem no refazer e conversa salva

Revision ID: d6f3a8b2c1e4
Revises: b4d2e7f1a9c3
Create Date: 2026-11-12 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd6f3a8b2c1e4'
down_revision: Union[str, None] = 'b4d2e7f1a9c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('mistake', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='open'))
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_question_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_question_source', 'question', ['source_question_id'], ['id'],
                                    ondelete='SET NULL')
    op.create_table(
        'chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=True),
        sa.Column('model', sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(['topic_id'], ['topic.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    _migrate_mistakes(op.get_bind())


def _migrate_mistakes(conn) -> None:
    """Dados de antes da v1.5: liga as cópias do "refazer" à questão original e junta os erros nela.

    1. Erro marcado como revisado → status "reviewed".
    2. Cada questão de um conjunto "refazer" aponta para a original (mesmo enunciado no conjunto de origem,
       seguindo a cadeia quando é refazer de refazer).
    3. As respostas das cópias, em ordem, decidem o status do erro da original: acertou → "fixed",
       errou → "again". O erro que tinha sido criado na cópia é juntado ao da original (minuto do vídeo
       e anotação vão junto se a original não tiver).
    """
    conn.execute(sa.text("UPDATE mistake SET status = 'reviewed' WHERE reviewed = 1"))

    sets = {r.id: r for r in conn.execute(sa.text(
        "SELECT id, attempt_type, source_set_id FROM question_set ORDER BY id")).fetchall()}
    by_set: dict[int, list] = {}
    for q in conn.execute(sa.text("SELECT id, question_set_id, statement FROM question ORDER BY id")).fetchall():
        by_set.setdefault(q.question_set_id, []).append(q)

    root_of: dict[int, int] = {}
    for set_id, s in sets.items():  # em ordem de id: a origem sempre vem antes
        if s.attempt_type != 'redo' or not s.source_set_id:
            continue
        source = {q.statement: q.id for q in by_set.get(s.source_set_id, [])}
        for q in by_set.get(set_id, []):
            original = source.get(q.statement)
            if original is None:
                continue
            root = root_of.get(original, original)
            root_of[q.id] = root
            conn.execute(sa.text("UPDATE question SET source_question_id = :r WHERE id = :q"), {"r": root, "q": q.id})

    if not root_of:
        return
    mistakes = {m.question_id: m for m in conn.execute(sa.text(
        "SELECT id, question_id, topic_id, video_minute, notes, status FROM mistake")).fetchall()}
    answers = conn.execute(sa.text(
        "SELECT a.question_id, a.is_correct FROM answer a ORDER BY a.created_at, a.id")).fetchall()
    for a in answers:
        root = root_of.get(a.question_id)
        if root is None:
            continue
        copy = mistakes.get(a.question_id)
        target = mistakes.get(root)
        if target is None and copy is not None:
            # Original sem erro registrado (raro): o erro da cópia passa a ser o da original
            conn.execute(sa.text("UPDATE mistake SET question_id = :r WHERE id = :m"), {"r": root, "m": copy.id})
            target, copy = copy, None
            mistakes[root] = target
        if target is None:
            continue
        if copy is not None:
            conn.execute(sa.text(
                "UPDATE mistake SET video_minute = COALESCE(video_minute, :v), notes = COALESCE(notes, :n) "
                "WHERE id = :m"), {"v": copy.video_minute, "n": copy.notes, "m": target.id})
            conn.execute(sa.text("DELETE FROM mistake WHERE id = :m"), {"m": copy.id})
            mistakes.pop(a.question_id, None)
        status = 'fixed' if a.is_correct else 'again'
        conn.execute(sa.text("UPDATE mistake SET status = :s, reviewed = 1 WHERE id = :m"),
                     {"s": status, "m": target.id})


def downgrade() -> None:
    op.drop_table('chat_message')
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint('fk_question_source', type_='foreignkey')
        batch_op.drop_column('source_question_id')
    with op.batch_alter_table('mistake', schema=None) as batch_op:
        batch_op.drop_column('status')
