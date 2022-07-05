from flask_login import UserMixin
from sqlalchemy import (
    Column,
    String,
)
from werkzeug.security import generate_password_hash, check_password_hash

from ambuda.models.base import Base, pk, foreign_key


class User(UserMixin, Base):
    """A user."""

    __tablename__ = "users"

    id = pk()
    #: The user's username.
    username = Column(String, nullable=False, unique=True)
    #: The user's hashed password.
    password_hash = Column(String, nullable=False)
    #: The user's email.
    email = Column(String, nullable=False, unique=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password) -> bool:
        return check_password_hash(self.password_hash, password)
