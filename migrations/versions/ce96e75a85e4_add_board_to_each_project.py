"""Add board to each project

Revision ID: ce96e75a85e4
Revises: aa1a6be51104
Create Date: 2022-07-26 07:30:42.411781

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base


# revision identifiers, used by Alembic.
revision = "ce96e75a85e4"
down_revision = "aa1a6be51104"
branch_labels = None
depends_on = None


# Define separate models to freeze the current setup at the time we wrote this
# migration.
Base = declarative_base()


class Project(Base):
    __tablename__ = "proof_projects"
    id = sa.Column(sa.Integer, primary_key=True)
    slug = sa.Column(sa.String, nullable=False)
    board_id = sa.Column(
        sa.Integer, sa.ForeignKey("discussion_boards.id"), nullable=False, index=True
    )


class Board(Base):
    __tablename__ = "discussion_boards"
    id = sa.Column(sa.Integer, primary_key=True)
    title = sa.Column(sa.String, nullable=False)


def upgrade() -> None:
    # Create as nullable column to prevent errors while we populate.
    op.add_column("proof_projects", sa.Column("board_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_proof_projects_board_id"), "proof_projects", ["board_id"], unique=False
    )

    bind = op.get_bind()
    session = orm.Session(bind=bind)
    for project in session.query(Project).all():
        board = Board(title=f"Board for {project.slug}")
        session.add(board)
        session.flush()
        project.board_id = board.id
    session.commit()

    # Make column non-null and add foreign key constraint.
    with op.batch_alter_table("proof_projects") as batch_op:
        batch_op.alter_column("board_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_proof_projects_board", "discussion_boards", ["board_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("proof_projects") as batch_op:
        batch_op.drop_constraint("fk_proof_projects_board", type_="foreignkey")
    op.drop_index(op.f("ix_proof_projects_board_id"), table_name="proof_projects")
    op.drop_column("proof_projects", "board_id")
