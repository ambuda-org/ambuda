#!/usr/bin/env bash

# Entrypoint for running the devserver from within Docker. Before running
# "make devserver", this file runs database setup / initialization scripts if a
# database has not already been created.


set -e

. /venv/bin/activate

export PATH=$PATH:/venv/bin/
export PYTHONPATH=$PYTHONPATH:/app

apt-get -qq update && apt-get -qq install -y git > /dev/null
python scripts/setup_database.py