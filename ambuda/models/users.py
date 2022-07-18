from flask_login import UserMixin
from sqlalchemy import (
    Column,
    String,
)
from werkzeug.security import generate_password_hash, check_password_hash

from ambuda.models.base import Base, pk


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
