#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.

set -e

# Run the devserver, and live reload our CSS and JS.
# "npx concurrently" does not work on Docker, but ./node_modules/.bin/concurrently does.
# We also need to add "--host=0.0.0.0" to "flask run" to allow the host to access the
# website that is running from the Docker container.
./node_modules/.bin/concurrently "flask run --host=0.0.0.0"
