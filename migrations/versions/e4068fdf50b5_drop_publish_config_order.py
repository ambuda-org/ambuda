"""drop publish_configs.order

Revision ID: e4068fdf50b5
Revises: 0593733b2590
Create Date: 2026-04-25

The displayed order of publish configs is now derived from each config's
filter (its image range), so the manually-curated `order` column is no
longer used.
"""

from alembic import op
import sqlalchemy as sa

revision = "e4068fdf50b5"
down_revision = "0593733b2590"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("publish_configs") as batch_op:
        batch_op.drop_column("order")


def downgrade() -> None:
    with op.batch_alter_table("publish_configs") as batch_op:
        batch_op.add_column(sa.Column("order", sa.Integer(), nullable=True))

    publish_configs = sa.table(
        "publish_configs",
        sa.column("id", sa.Integer),
        sa.column("project_id", sa.Integer),
        sa.column("order", sa.Integer),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.select(publish_configs.c.id, publish_configs.c.project_id).order_by(
            publish_configs.c.project_id, publish_configs.c.id
        )
    ).fetchall()

    counters: dict[int, int] = {}
    for row in rows:
        idx = counters.get(row.project_id, 0)
        conn.execute(
            publish_configs.update()
            .where(publish_configs.c.id == row.id)
            .values(order=idx)
        )
        counters[row.project_id] = idx + 1

    with op.batch_alter_table("publish_configs") as batch_op:
        batch_op.alter_column("order", nullable=False)
