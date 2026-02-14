"""Add project_sources table

Revision ID: c7d8e9f0a1b2
Revises: b4c5d6e7f8a9
Create Date: 2026-02-13 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7d8e9f0a1b2"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["proof_projects.id"]),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_sources_project_id"),
        "project_sources",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_sources_author_id"),
        "project_sources",
        ["author_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_project_sources_author_id"), table_name="project_sources")
    op.drop_index(op.f("ix_project_sources_project_id"), table_name="project_sources")
    op.drop_table("project_sources")
