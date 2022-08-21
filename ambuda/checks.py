"""Sanity checks that run on application startup."""


import sys

from click import style
from sqlalchemy import create_engine
from sqlalchemy import inspect

from ambuda.models.base import Base


def _warn(text: str = ""):
    """Print a warning message to the terminal."""
    print(style(text, fg="red"))


def check_app_schema_matches_db_schema(database_uri: str):
    """Check that our application tables and database tables match.

    Currently, we apply the following checks:
    - All app tables exist in the database.
    - A given app table and its corresponding database table have the same
      column names.

    If any check fails, exit gracefully and tell the user how to resolve the
    issue.

    :param database_uri:
    """

    engine = create_engine(database_uri)
    inspector = inspect(engine)

    errors = []

    for table_name, table in Base.metadata.tables.items():
        app_column_names = set(table.columns.keys())
        db_column_names = {c["name"] for c in inspector.get_columns(table_name)}

        if not db_column_names:
            errors.append(f'Table "{table_name}" found in app, missing in db')
            continue

        for col in app_column_names:
            if col not in db_column_names:
                errors.append(
                    f'Column "{table_name}.{col}" found in app, missing in db'
                )

        for col in db_column_names:
            if col not in app_column_names:
                errors.append(
                    f'Column "{table_name}.{col}" found in db, missing in app'
                )

    if errors:
        _warn("The data tables defined in your application code don't match the")
        _warn("tables defined in your database. Usually, this means that you need")
        _warn("to upgrade your database schemas. You can do so by running:")
        _warn()
        _warn("    alembic upgrade head")
        _warn()
        _warn("For more information, see our official docs at:")
        _warn()
        _warn("    https://ambuda.readthedocs.io/en/latest/managing-the-database.html")
        _warn()
        _warn("If the error persists, please ping the #backend channel on the")
        _warn("Ambuda Discord server (https://discord.gg/7rGdTyWY7Z).")
        _warn()
        _warn("Errors found:")
        for error in errors:
            _warn(f"- {error}")
        sys.exit(1)
    else:
        print("Database check OK")
