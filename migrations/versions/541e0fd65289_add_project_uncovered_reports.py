"""add project_uncovered_reports

Revision ID: 541e0fd65289
Revises: e4068fdf50b5
Create Date: 2026-04-25

Stores cached output of the expensive `find_uncovered_blocks` analysis, run
on demand from the admin "unpublished projects" page.
"""

from alembic import op
import sqlalchemy as sa


revision = "541e0fd65289"
down_revision = "e4068fdf50b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "proof_project_uncovered_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("proof_projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(),
            nullable=False,
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("proof_project_uncovered_reports")
