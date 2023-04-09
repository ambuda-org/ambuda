"""Add Project metadata fields

Revision ID: f208e1844a36
Revises: ed1c7e4af52d
Create Date: 2023-04-07 19:15:04.082171

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f208e1844a36"
down_revision = "ed1c7e4af52d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "genres",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    with op.batch_alter_table("proof_projects") as batch_op:
        batch_op.alter_column("title", new_column_name="display_title")
        batch_op.create_foreign_key(
            "fk_proof_projects_genre_id", "proof_projects", ["genre_id"], ["id"]
        )

    op.add_column(
        "proof_projects",
        sa.Column("print_title", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("worldcat_link", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "proof_projects",
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column("proof_projects", sa.Column("genre_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_proof_projects_genre_id"), "proof_projects", ["genre_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_proof_projects_genre_id"), table_name="proof_projects")
    op.drop_column("proof_projects", "notes")
    op.drop_column("proof_projects", "worldcat_link")
    op.drop_column("proof_projects", "print_title")
    op.drop_column("proof_projects", "genre_id")

    with op.batch_alter_table("proof_projects") as batch_op:
        batch_op.alter_column("display_title", new_column_name="title")

    op.drop_table("genres")
