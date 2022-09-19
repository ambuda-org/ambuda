"""Add project creator and timestamps

Revision ID: 82cf1fd072bb
Revises: 66f49d23146f
Create Date: 2022-08-13 07:14:52.325324

"""
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "82cf1fd072bb"
down_revision = "66f49d23146f"
branch_labels = None
depends_on = None


Base = sa.orm.declarative_base()


class Project(Base):
    __tablename__ = "proof_projects"
    id = sa.Column(sa.Integer, primary_key=True)
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = sa.Column(sa.DateTime, default=datetime.utcnow, nullable=False)


def upgrade() -> None:
    # Create as non-null, add default values, then update to not-null.
    op.add_column(
        "proof_projects", sa.Column("created_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "proof_projects", sa.Column("updated_at", sa.DateTime(), nullable=True)
    )

    op.add_column(
        "proof_projects", sa.Column("creator_id", sa.Integer(), nullable=True)
    )
    op.create_index(
        op.f("ix_proof_projects_creator_id"),
        "proof_projects",
        ["creator_id"],
        unique=False,
    )

    # Add defalut timestamps for all existing projects.
    now = datetime.utcnow()
    bind = op.get_bind()
    session = sa.orm.Session(bind=bind)
    for project in session.query(Project).all():
        project.created_at = now
        project.updated_at = now
        session.add(project)
    session.commit()

    with op.batch_alter_table("proof_projects") as batch_op:
        batch_op.create_foreign_key(
            "fk_proof_projects_creator_id_users", "users", ["creator_id"], ["id"]
        )
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=False)
        batch_op.alter_column("updated_at", existing_type=sa.DATETIME(), nullable=False)


def downgrade() -> None:
    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    }
    with op.batch_alter_table(
        "proof_projects", naming_convention=naming_convention
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_proof_projects_creator_id_users", type_="foreignkey"
        )
        # batch_op.drop_constraint('fk_proof_projects_creator_id_users', type_="foreignkey")
    op.drop_index(op.f("ix_proof_projects_creator_id"), table_name="proof_projects")
    op.drop_column("proof_projects", "creator_id")
    op.drop_column("proof_projects", "updated_at")
    op.drop_column("proof_projects", "created_at")
