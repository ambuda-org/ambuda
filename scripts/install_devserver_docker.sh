#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.

set -e

# Extract file path from sqlite:///[file path]
DB_FILE_PATH="${SQLALCHEMY_DATABASE_URI/sqlite:\/\/\//}"

# Initialize database if the database file doesn't already exist.
if [ ! -f $DB_FILE_PATH ]; then

    echo "Initializing database at $DB_FILE_PATH..."

    # Create tables
    python -m scripts.initialize_db

    # Add some starter data with a few basic seed scripts.
    make db-seed-ci

    # Create Alembic's migrations table.
    alembic ensure_version

    # Set the most recent revision as the current one.
    alembic stamp head

fi

# Update to the latest migration.
python -m ambuda.seed.lookup
alembic upgrade head
