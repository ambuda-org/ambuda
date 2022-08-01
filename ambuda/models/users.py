from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    String,
)
from werkzeug.security import generate_password_hash, check_password_hash

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

    def set_password(self, raw_password: str):
        """Hash and save the given password."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check if the given password matches the user's hash."""
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        # FIXME: Don't hardcode the admin user here. Use user roles instead.
        return self.username == "akprasad"


class PasswordResetTokens(Base):
    """Models a "forgot password" recovery token."""

    __tablename__ = "auth_password_reset_tokens"

    #: Primary key.
    id = pk()
    #: The user this token belongs to.
    user_id = foreign_key("users.id")
    #: The hashed recovery token.
    #: - Index so that we can find specific links by code.
    #: - Hash so that accounts aren't compromised if the database leaks.
    token_hash = Column(String, nullable=False, index=True)
    #: Whether the link is still active or not. (Once used, we should
    #: deactivate / delete this link.)
    is_active = Column(Boolean, nullable=False)
    #: Timestamp at which this link was created. Links expire after X days.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
