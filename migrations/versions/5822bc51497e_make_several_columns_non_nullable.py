"""Make several columns non-nullable

Revision ID: 5822bc51497e
Revises: deb7c1bae659
Create Date: 2022-07-22 18:31:58.697625

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "5822bc51497e"
down_revision = "deb7c1bae659"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("proof_pages") as batch_op:
        batch_op.alter_column("version", existing_type=sa.INTEGER(), nullable=False)
    with op.batch_alter_table("proof_revisions") as batch_op:
        batch_op.alter_column("status_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("created", existing_type=sa.DATETIME(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("proof_revisions") as batch_op:
        batch_op.alter_column("created", existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column("status_id", existing_type=sa.INTEGER(), nullable=True)
    with op.batch_alter_table("proof_pages") as batch_op:
        batch_op.alter_column("version", existing_type=sa.INTEGER(), nullable=True)
