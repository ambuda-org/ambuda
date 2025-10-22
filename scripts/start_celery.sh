#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.


set -e

uv run celery -A ambuda.tasks worker --loglevel=INFO
