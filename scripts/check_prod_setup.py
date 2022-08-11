"""Verifies that the local `.env` file is a is well-formed production config.

NOTE: run this script in the production environment.
"""

import config
from config import create_config_only_app

# Fails if config is malformed.
app = create_config_only_app("production")
