#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.

set -e
source env/bin/activate
source .env

# Extract file path from sqlite:///[file path]
DB_FILE_PATH="${SQLALCHEMY_DATABASE_URI/sqlite:\/\/\//}"

# Initialize database if the database file doesn't already exist.
if [ ! -f $DB_FILE_PATH ]; then

    echo "Initializing database at $DB_FILE_PATH..."
    echo ">> Create $(dirname ${DB_FILE_PATH})"
    mkdir -p $(dirname ${DB_FILE_PATH})

    # Create tables
    python -m scripts.initialize_db

    # Add some starter data with a few basic seed scripts.
    python -m ambuda.seed.lookup && python -m ambuda.seed.texts.gretil && python -m ambuda.seed.dcs

    # Create Alembic's migrations table.
    /venv/bin/alembic ensure_version

    # Set the most recent revision as the current one.
    /venv/bin/alembic stamp head

fi

# Update to the latest migration.
python -m ambuda.seed.lookup
/venv/bin/alembic upgrade head

# Run the devserver, and live reload our CSS and JS.
# "npx concurrently" does not work on Docker, but ./node_modules/.bin/concurrently does.
# We also need to add "--host=0.0.0.0" to "flask run" to allow the host to access the
# website that is running from the Docker container.
./node_modules/.bin/concurrently "flask run --host=0.0.0.0" "make css-dev" "make js-dev"
