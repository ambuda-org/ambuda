from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship
from werkzeug.security import generate_password_hash, check_password_hash

from ambuda.enums import SiteRole
from ambuda.models.base import Base, pk, foreign_key


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


class PasswordResetToken(Base):

    """Models a "forgot password" recovery token."""

    __tablename__ = "auth_password_reset_tokens"

    #: Primary key.
    id = pk()
    #: The user this token belongs to.
    user_id = foreign_key("users.id")
    #: The hashed recovery token.
    #: - Index so that we can find specific links by code.
    #: - Hash so that accounts aren't compromised if the database leaks.
    token_hash = Column(String, nullable=False, unique=True)
    #: Whether the link is still active or not. (Once used, we should
    #: deactivate / delete this token.)
    is_active = Column(Boolean, default=True, nullable=False)
    #: Timestamp at which this token was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Timestamp at which this token was used.
    used_at = Column(DateTime, nullable=True)

    def set_token(self, raw_token: str):
        """Hash and save the given token."""
        self.token_hash = generate_password_hash(raw_token)

    def check_token(self, raw_token: str) -> bool:
        """Check if the given token matches the user's hash."""
        return check_password_hash(self.token_hash, raw_token)
