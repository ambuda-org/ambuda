"""Base model and utilities."""

from sqlalchemy import Column, ForeignKey, Integer
from sqlalchemy.orm import declarative_base

#: The base class for all of Ambuda's models. All new models should inherit
#: from this class.
Base = declarative_base()


def pk():
    """Define a simple integer primary key."""
    return Column(Integer, primary_key=True, autoincrement=True)


def foreign_key(field: str):
    """Define a simple foreign key."""
    return Column(Integer, ForeignKey(field), nullable=False, index=True)


def same_as(column_name: str):
    """Utility for setting one column's default value to another column."""

    def default_function(context):
        return context.current_parameters.get(column_name)

    return default_function
