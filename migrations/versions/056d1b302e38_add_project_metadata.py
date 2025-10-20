"""Add project metadata

Revision ID: 056d1b302e38
Revises: 6c87b647ecaa
Create Date: 2022-07-19 21:31:19.974524

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "056d1b302e38"
down_revision = "6c87b647ecaa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proof_projects",
        sa.Column("author", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("editor", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("publisher", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("publication_year", sa.String(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("proof_projects", "publication_year")
    op.drop_column("proof_projects", "publisher")
    op.drop_column("proof_projects", "editor")
    op.drop_column("proof_projects", "author")
