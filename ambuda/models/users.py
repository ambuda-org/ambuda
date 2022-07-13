from enum import Enum
from flask_login import UserMixin
from sqlalchemy import (
    Column,
    String,
)
from sqlalchemy.sql.sqltypes import Integer
from werkzeug.security import generate_password_hash, check_password_hash

from ambuda.models.base import Base, pk, foreign_key

# The set of permissions for a user are determined via bitwise AND
# of the permissions value and each role below. This means each value
# must be a power of 2.
class UserPermissions(Enum):
    VIEWER = 0
    ADMIN = 1

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
    #: The user's permissions across the system.
    permissions = Column(Integer, nullable=False, default=UserPermissions.VIEWER.value)

    def set_password(self, raw_password: str):
        """Hash and save the given password."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Check if the given password matches the user's hash."""
        return check_password_hash(self.password_hash, raw_password)
    
    def set_permission(self, permission: UserPermissions):
        """Set the bitwise field for the given permission for the user."""
        self.permissions = self.permissions + permission.value

    def unset_permission(self, permission: UserPermissions):
        """Unset the bitwise field for the given permission for the user."""
        self.permissions = self.permissions - permission.value
    
    def check_permission(self, permission: UserPermissions) -> bool:
        """Check if a user has the given permission. """
        return self.permissions & permission.value

    @property
    def is_admin(self):
        return self.check_permission(UserPermissions.ADMIN)
