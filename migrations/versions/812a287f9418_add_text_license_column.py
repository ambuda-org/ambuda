"""add text license column

Revision ID: 812a287f9418
Revises: b7b4e7429b9f
Create Date: 2026-04-02

Add a nullable `license` column to the texts table.
For texts that have a source project, set the license to "CC0 1.0".
"""

from alembic import op
import sqlalchemy as sa

revision = "812a287f9418"
down_revision = "b7b4e7429b9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("texts", sa.Column("license", sa.String(), nullable=True))

    # Set license for all texts that have a linked proof project.
    texts = sa.table(
        "texts",
        sa.column("id", sa.Integer),
        sa.column("license", sa.String),
        sa.column("project_id", sa.Integer),
    )
    op.execute(
        texts.update().where(texts.c.project_id.isnot(None)).values(license="CC0 1.0")
    )


def downgrade() -> None:
    op.drop_column("texts", "license")
