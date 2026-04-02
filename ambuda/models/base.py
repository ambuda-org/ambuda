"""Base model and utilities."""

from sqlalchemy import Column, ForeignKey, Integer, MetaData
from sqlalchemy.orm import DeclarativeBase

convention = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


#: The base class for all of Ambuda's models. All new models should inherit
#: from this class.
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=convention)


def pk():
    """Define a simple integer primary key."""
    return Column(Integer, primary_key=True, autoincrement=True)


def foreign_key(field: str, nullable=False, ondelete=None):
    """Define a simple foreign key."""
    return Column(
        Integer, ForeignKey(field, ondelete=ondelete), nullable=nullable, index=True
    )


def same_as(column_name: str):
    """Utility for setting one column's default value to another column."""

    def default_function(context):
        return context.current_parameters.get(column_name)

    return default_function
