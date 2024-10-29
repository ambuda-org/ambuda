"""Add project description and page numbers

Revision ID: 66f49d23146f
Revises: 0d3fce7c5341
Create Date: 2022-08-06 07:50:07.711246

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "66f49d23146f"
down_revision = "0d3fce7c5341"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proof_projects",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("page_numbers", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("proof_projects", "page_numbers")
    op.drop_column("proof_projects", "description")
