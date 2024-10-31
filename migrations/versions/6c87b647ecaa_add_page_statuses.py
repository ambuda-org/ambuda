"""Add page statuses

Revision ID: 6c87b647ecaa
Revises: b3cf424f4ce5
Create Date: 2022-07-18 20:45:22.600084

"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.enums import SitePageStatus
from ambuda.seed.utils.data_utils import create_db

# revision identifiers, used by Alembic.
revision = "6c87b647ecaa"
down_revision = "b3cf424f4ce5"
branch_labels = None
depends_on = None


def get_default_id():
    """Used in the `add_page_statuses` migration."""
    engine = create_db()
    with Session(engine) as session:
        return session.query(db.PageStatus).filter_by(name=SitePageStatus.R0).one


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

    # Create roles
    from ambuda import config

    flask_env = os.environ["FLASK_ENV"]
    conf = config.load_config_object(flask_env)
    engine = sa.create_engine(conf.SQLALCHEMY_DATABASE_URI)
    with sa.Session(engine) as session:
        statuses = session.query(db.PageStatus).all()
        existing_names = {s.name for s in statuses}
        new_names = {n.value for n in SitePageStatus if n not in existing_names}

        if new_names:
            for name in new_names:
                status = db.PageStatus(name=name)
                session.add(status)
            session.commit()
    # End create roles

    default_id = str(get_default_id())

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
