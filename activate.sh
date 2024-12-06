#!/bin/bash
set -euo pipefail

# Activate the virtual environment.
source env/bin/activate

# "$@" expands to all arguments passed to the script
make "$@"
deactivate
