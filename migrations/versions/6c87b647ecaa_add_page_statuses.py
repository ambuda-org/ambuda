"""Add page statuses

Revision ID: 6c87b647ecaa
Revises: b3cf424f4ce5
Create Date: 2022-07-18 20:45:22.600084

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.seed.lookup.page_status
from ambuda.seed.utils.data_utils import create_db

# revision identifiers, used by Alembic.
revision = "6c87b647ecaa"
down_revision = "b3cf424f4ce5"
branch_labels = None
depends_on = None


def _update_existing_pages():
    engine = create_db()

    with Session(engine) as session:
        default_status = session.query(db.PageStatus).filter_by(name="reviewed-0").one()
        default_id = default_status.id
        assert default_id

        for row in session.query(db.Page).all():
            row.status_id = default_id
        session.commit()


def upgrade() -> None:
    op.create_table(
        "page_statuses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
    )
    ambuda.seed.lookup.page_status.run()
    default_id = str(ambuda.seed.lookup.page_status.get_default_id())

    op.add_column(
        "proof_pages",
        sa.Column("status_id", sa.Integer(), nullable=False, server_default=default_id),
    )
    _update_existing_pages()

    op.create_index(
        op.f("ix_proof_pages_status_id"), "proof_pages", ["status_id"], unique=False
    )
    with op.batch_alter_table("proof_pages") as batch_op:
        batch_op.create_foreign_key(
            "proof_pages", "proof_page_statuses", ["status_id"], ["id"]
        )


def downgrade() -> None:
    op.drop_table("page_statuses")
    with op.batch_alter_table("proof_pages") as batch_op:
        batch_op.drop_constraint("proof_pages", type_="foreignkey")
    op.drop_index(op.f("ix_proof_pages_status_id"), table_name="proof_pages")
    op.drop_column("proof_pages", "status_id")
