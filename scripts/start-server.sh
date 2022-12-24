#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.


set -e

. /venv/bin/activate

export PATH=$PATH:/venv/bin/

# Extract file path from sqlite:///[file path]

DB_FILE_PATH="${SQLALCHEMY_DATABASE_URI/sqlite:\/\/\//}"

echo "Loading Database from $DB_FILE_PATH"

# Update to the latest migration.
python -m ambuda.seed.lookup

/venv/bin/alembic upgrade head

# Run the devserver, and live reload our CSS and JS.
# "npx concurrently" does not work on Docker, but ./node_modules/.bin/concurrently does.
# We also need to add "--host=0.0.0.0" to "flask run" to allow the host to access the
# website that is running from the Docker container.
echo "Flask start from /venv/bin/flask with 0.0.0.0 on port 5000"
./node_modules/.bin/concurrently "/venv/bin/flask run -h 0.0.0.0 -p 5000"

