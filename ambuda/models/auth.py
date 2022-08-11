from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from ambuda.enums import SiteRole
from ambuda.models.base import Base, pk, ForeignKey


class User(UserMixin, Base):
    """A user."""

    __tablename__ = "users"

    #: Primary key.
    id = pk()
    #: The user's username.
    username = Column(String, nullable=False, unique=True)
    #: The user's hashed password.
    password_hash = Column(String, nullable=False)
    #: The user's email.
    email = Column(String, nullable=False, unique=True)
    #: Timestamp at which this user record was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    #: All roles available for this user.
    roles = relationship("Role", secondary="user_roles")

    def set_password(self, raw_password: str):
        """Hash and save the given password."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check if the given password matches the user's hash."""
        return check_password_hash(self.password_hash, raw_password)

    def has_role(self, role: SiteRole) -> bool:
        return role.value in {r.name for r in self.roles}

    @property
    def is_admin(self) -> bool:
        return self.has_role(SiteRole.ADMIN)

    @property
    def is_proofreader(self) -> bool:
        return self.has_role(SiteRole.P1) or self.has_role(SiteRole.P2)


class Role(Base):

    """A role"""

    __tablename__ = "roles"

    #: Primary key.
    id = pk()
    #: Name of the role.
    name = Column(String, unique=True, nullable=False)
    #: When this role was defined.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Role({self.id}, {self.name!r})>"


class UserRoles(Base):

    """Secondary table for users and roles."""

    __tablename__ = "user_roles"

    #: The user that has this role.
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)
    #: The role the user has.
    role_id = Column(Integer, ForeignKey("roles.id"), primary_key=True, index=True)
