"""Base model and utilities."""

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
)
from sqlalchemy.orm import (
    declarative_base,
)


Base = declarative_base()


def pk():
    """A simple integer primary key."""
    return Column(Integer, primary_key=True, autoincrement=True)


def foreign_key(field):
    """A simple foreign key."""
    return Column(Integer, ForeignKey(field), nullable=False, index=True)
