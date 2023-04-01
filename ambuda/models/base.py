"""Base model and utilities."""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, ForeignKey, Integer

# TODO(arun): rename and standardize this across the project. Avoid confusion
# with the `database` module, which is usually imported as `db`.
db = SQLAlchemy(session_options=dict(autoflush=False, autocommit=False))


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
