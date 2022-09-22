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
    make db-seed-basic

    # Create Alembic's migrations table.
    alembic ensure_version

    # Set the most recent revision as the current one.
    alembic stamp head

fi

# Update to the latest migration.
python -m ambuda.seed.lookup
alembic upgrade head

pwd
ls .
ls ./node_modules
ls ./node_modules/.bin

# Run the devserver, and live reload our CSS and JS.
# "npx concurrently" does not work on Docker, but ./node_modules/.bin/concurrently does.
# We also need to add "--host=0.0.0.0" to "flask run" to allow the host to access the
# website that is running from the Docker container.
./node_modules/.bin/concurrently "flask run --host=0.0.0.0" "make css-dev" "make js-dev"
