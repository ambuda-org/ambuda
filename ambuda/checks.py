"""Sanity checks that run on application startup."""

import sys

from click import style
from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import Column

from ambuda import consts, enums
from ambuda import database as db
from ambuda import queries as q
from ambuda.models.base import db as flask_sqla


def _warn(text: str = ""):
    """Print a warning message to the terminal."""
    print(style(text, fg="red"), file=sys.stderr)


def _full_column_name(table_name: str, col: str) -> str:
    return f"{table_name}.{col}"


def _check_column(app_col: Column, db_col: dict[str, str]) -> list[str]:
    full_name = _full_column_name(app_col.table.name, app_col.name)
    errors = []

    if app_col.nullable and not db_col["nullable"]:
        errors.append(f'Column "{full_name}" is nullable in the app but not in the db.')
    elif db_col["nullable"] and not app_col.nullable:
        errors.append(f'Column "{full_name}" is nullable in the db but not in the app.')

    if app_col.primary_key and not db_col["primary_key"]:
        errors.append(
            f'Column "{full_name}" is a primary key in the app but not in the db.'
        )
    elif db_col["primary_key"] and not app_col.primary_key:
        errors.append(
            f'Column "{full_name}" is a primary key in the db but not in the app.'
        )

    return errors


def _check_app_schema_matches_db_schema(database_uri: str) -> list[str]:
    """Check that our application tables and database tables match.

    Currently, we apply the following checks:

    - All app tables exist in the database.
    - A given app table and its corresponding database table have the same
      column names.
    - A given app columns and its database column have equal `nullable` and
      `primary_key` status.

    Here are some important checks that we haven't implemented yet:

    - Column have equal types.
    - Column have equal default values.
    - Column have equal indices.

    If any check fails, exit gracefully and tell the user how to resolve the
    issue.

    :param database_uri:
    """

    engine = create_engine(database_uri)
    inspector = inspect(engine)

    errors = []

    for table_name, table in flask_sqla.Model.metadata.tables.items():
        app_columns = table.columns
        db_columns = {c["name"]: c for c in inspector.get_columns(table_name)}

        app_column_names = set(app_columns.keys())
        db_column_names = set(db_columns.keys())

        if not db_column_names:
            errors.append(f'Table "{table_name}" found in app but missing in db.')
            continue

        for col in app_column_names:
            if col not in db_column_names:
                full_name = _full_column_name(table_name, col)
                errors.append(f'Column "{full_name}" found in app but missing in db.')

        for col in db_column_names:
            if col not in app_column_names:
                full_name = _full_column_name(table_name, col)
                errors.append(f'Column "{full_name}" found in db but missing in app.')

        for col in app_column_names & db_column_names:
            app_col = app_columns[col]
            db_col = db_columns[col]
            full_name = _full_column_name(table_name, col)

            column_errors = _check_column(app_col, db_col)
            if column_errors:
                errors.extend(column_errors)

    return errors


def _check_lookup_tables(session) -> list[str]:
    lookups = [
        (enums.SitePageStatus, db.PageStatus),
        (enums.SiteRole, db.Role),
    ]

    errors = []
    for enum, model in lookups:
        items = session.query(model).all()
        db_names = {x.name for x in items}
        app_names = {x.value for x in enum}

        enum_name = enum.__name__
        table_name = model.__tablename__
        for field_name in db_names - app_names:
            errors.append(
                f'Enum field "{enum_name}.{field_name}" not defined on database table "{table_name}".'
            )

        for field_name in app_names - db_names:
            errors.append(
                f'Table row ({table_name} where name = "{field_name}") not defined on enum "{enum_name}".'
            )

    return errors


def _check_bot_user(session) -> list[str]:
    """Check that the ambuda-bot user exists."""
    username = consts.BOT_USERNAME
    # Assume bot user is active
    bot_user = session.query(db.User).filter_by(username=username).first()
    if bot_user:
        return []
    else:
        return [f'Bot user "{username}" does not exist.']


def check_database(database_uri: str):
    errors = _check_app_schema_matches_db_schema(database_uri)

    session = q.get_session()
    errors += _check_lookup_tables(session)
    errors += _check_bot_user(session)

    if errors:
        _warn("The data tables defined in your application code don't match the")
        _warn("tables defined in your database. Usually, this means that you need")
        _warn("to upgrade your setup. You can do so by running:")
        _warn()
        _warn("    make upgrade")
        _warn()
        _warn("Specific errors are:")
        _warn()
        for error in errors:
            _warn(f"- {error}")
        _warn()
        _warn("For more information, see our official docs at:")
        _warn()
        _warn("    https://ambuda.readthedocs.io/en/latest/managing-the-database.html")
        _warn()
        _warn("If the error persists, please ping the #backend channel on the")
        _warn("Ambuda Discord server (https://discord.gg/7rGdTyWY7Z).")
        sys.exit(1)
    else:
        # Style the output to match Flask's styling.
        print(" * [OK] Ambuda database check has passed.", flush=True)
