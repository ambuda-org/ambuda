"""create user permission table

Revision ID: 0d3fce7c5341
Revises: 056d1b302e38
Create Date: 2022-07-22 00:20:54.155505

"""

from datetime import datetime
from enum import Enum

from alembic import op
import sqlalchemy as sa
from sqlalchemy import orm


# revision identifiers, used by Alembic.
revision = "0d3fce7c5341"
down_revision = "5ac51663112f"
branch_labels = None
depends_on = None

Base = orm.declarative_base()


class SiteRole(Enum):
    P1 = "p1"


class User(Base):
    __tablename__ = "users"
    id = sa.Column(sa.Integer, primary_key=True)


class Role(Base):
    __tablename__ = "roles"
    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String, unique=True, nullable=False)
    created_at = sa.Column(sa.DateTime, nullable=False, default=datetime.utcnow)


class UserRoles(Base):
    __tablename__ = "user_roles"
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("users.id"),
        nullable=False,
        primary_key=True,
        index=True,
    )
    role_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("roles.id"),
        nullable=False,
        primary_key=True,
        index=True,
    )


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, default=datetime.utcnow),
    )
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id"),
            nullable=False,
            primary_key=True,
            index=True,
        ),
        sa.Column(
            "role_id",
            sa.Integer,
            sa.ForeignKey("roles.id"),
            nullable=False,
            primary_key=True,
            index=True,
        ),
    )
    # generate roles for users
    with orm.Session(bind=op.get_bind()) as session:
        # Create proofreader role.
        proofreader_role = Role(name=SiteRole.P1.value)
        session.add(proofreader_role)
        session.flush()

        # Add all existing users as proofreaders
        for user in session.query(User).all():
            user_role_proofreader = UserRoles(
                user_id=user.id, role_id=proofreader_role.id
            )
            session.add(user_role_proofreader)

        session.commit()


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_table("roles")
