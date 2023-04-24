"""Models related to user authentication and authorization."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Text as Text_
from sqlalchemy.orm import relationship
from werkzeug.security import check_password_hash, generate_password_hash

from ambuda.models.base import Base, foreign_key, pk
from ambuda.utils.user_mixins import AmbudaUserMixin


class User(AmbudaUserMixin, Base):
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

    #: The user's self-description.
    description = Column(Text_, nullable=False, default="")

    #: If the user deleted their account.
    is_deleted = Column(Boolean, nullable=False, default=False)

    #: If the user was banned..
    is_banned = Column(Boolean, nullable=False, default=False)

    #: If the user has verified their email.
    is_verified = Column(Boolean, nullable=False, default=False)

    #: All roles available for this user.
    roles = relationship("Role", secondary="user_roles")

    def __str__(self):
        return self.username

    def __repr__(self):
        username = self.username
        return f'<User(username="{username}")>'

    def set_password(self, raw_password: str):
        """Hash and save the given password."""
        self.password_hash = generate_password_hash(raw_password)

    def set_is_deleted(self, is_deleted: bool):
        """Update is_deleted."""
        self.is_deleted = is_deleted

    def set_is_banned(self, is_banned: bool):
        """Update is_banned."""
        self.is_banned = is_banned

    def set_is_verified(self, is_verified: bool):
        """Update is_verified."""
        self.is_verified = is_verified

    def check_password(self, raw_password: str) -> bool:
        """Check if the given password matches the user's hash."""
        return check_password_hash(self.password_hash, raw_password)


class Role(Base):

    """A role.

    Roles are how we model fine-grained permissions on Ambuda.
    """

    __tablename__ = "roles"

    #: Primary key.
    id = pk()
    #: Name of the role.
    name = Column(String, unique=True, nullable=False)
    #: When this role was defined.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<Role({self.id}, {self.name!r})>"


class UserStatusLog(AmbudaUserMixin, Base):
    """Tracks changes to user statuses."""

    __tablename__ = "user_status_log"

    #: Primary key.
    id = pk()

    #: The user whose status was changed.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    #: Timestamp at which this status change occured.
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    #: Describes the status change that occurred.
    change_description = Column(String, nullable=False)

    #: When should this status change expire/revert, defaults to never.
    expiry = Column(DateTime, default=None, nullable=True)

    @property
    def is_expired(self) -> bool:
        """Check if the action has expired."""
        return self.expiry and self.expiry < datetime.utcnow()

    @property
    def is_temporary(self) -> bool:
        """
        Check if the action has an expiry and will be reverted
        in the future.
        """
        return self.expiry


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
