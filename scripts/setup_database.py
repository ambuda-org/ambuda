#! /usr/bin/python3
"""Initializes the development database by creating all tables.

This module is used in `scripts/initialize_from_scratch.sh`.

TODO: what are the implications of running `create_all` on app startup?
"""

import subprocess
from os.path import exists as file_exists

from dotenv import load_dotenv
from sqlalchemy import create_engine

import config
from ambuda import database as db
from ambuda.seed import dcs, lookup, texts

# TODO: need to FIX
from ambuda.seed.dictionaries import monier  # noqa

# TODO: need to FIX
from ambuda.seed.texts import gretil  # noqa


def get_sql_uri():
    """get sql alchemy uri"""

    conf = config.load_config_object("development")
    sql_uri = conf.SQLALCHEMY_DATABASE_URI
    return sql_uri


def get_db_file_path(sql_uri):
    """get file path from sql alchemy uri"""

    db_file_path = sql_uri.replace("sqlite:///", "")
    if db_file_path == sql_uri:
        print(f"Error! Invalid SQLALCHEMY_DATABASE_URI {sql_uri}")
    return db_file_path


def run_module(module_name):
    print(f'{"#"}' * 20)
    print(f"Intializing {module_name}")
    if not module_name.run():
        print(f"Error! {module_name}.run() failed")
        return False
    print(f"{module_name} initialization successful!")
    print(f'{"#"}' * 20)
    return True


def init_database(sql_uri, db_file_path):
    """Initialize database"""

    print(f"Initializing database at {db_file_path}...")
    # Create tables
    engine = create_engine(sql_uri)
    db.Base.metadata.create_all(engine)

    if not run_module(lookup):
        return False

    if not run_module(texts.gretil):
        return False

    if not run_module(dcs):
        return False

    if not run_module(monier):
        return False

    if not alembic_migrations():
        return False

    print(f"Success! Database initialized at {db_file_path}")
    return True


def alembic_migrations():
    try:
        subprocess.run(["/venv/bin/alembic", "ensure_version"])
    except subprocess.CalledProcessError as err:
        print(f"Error processing alembic ensure_versions - {err}")
        return False
    try:
        subprocess.run(["/venv/bin/alembic", "stamp", "head"])
    except subprocess.CalledProcessError as err:
        print(f"Error processing alembic stamp head - {err}")
        return False
    return True


def setup_database(db_file_path):
    """Lookup and Update to the latest migration."""
    if not file_exists(db_file_path):
        print(f"Database found at {db_file_path}...")
        return False

    if not lookup.run():
        print("Error! lookup.run() failed")
        return False

    # Set the most recent revision as the current one.
    subprocess.run(["/venv/bin/alembic", "upgrade", "head"])
    print(f"Success! Database setup at {db_file_path}")
    return True


def run():
    """
    Initialize db for fresh installs. Bootup db on restarts
    """

    load_dotenv()
    sql_uri = get_sql_uri()
    try:
        db_file_path = get_db_file_path(sql_uri)
    except Exception as err:
        print(f"Failed to get db path - {err}")

    if file_exists(db_file_path):
        print(f"Database found at {db_file_path}..")
        ret_setup = setup_database(db_file_path)
        if not ret_setup:
            print(f"Error! Database setup at {db_file_path}..")
            return False
    else:
        print("Initialize Database not found")
        ret_init = init_database(sql_uri, db_file_path)
        if not ret_init:
            print(f"Error! Database setup at {db_file_path}..")
            return False
    return True


if __name__ == "__main__":
    run()
