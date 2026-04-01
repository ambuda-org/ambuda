"""Add text_alternate_titles table

Revision ID: 4ab32672bbc9
Revises: 86b67aeb9dce
Create Date: 2026-03-31 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "4ab32672bbc9"
down_revision = "86b67aeb9dce"


def upgrade() -> None:
    op.create_table(
        "text_alternate_titles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("text_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["text_id"], ["texts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_text_alternate_titles_title"), "text_alternate_titles", ["title"]
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_text_alternate_titles_title"), table_name="text_alternate_titles"
    )
    op.drop_table("text_alternate_titles")
