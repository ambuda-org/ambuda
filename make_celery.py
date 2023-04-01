"""Entrypoint for Celery runner."""


import os

from dotenv import load_dotenv

from ambuda import create_app

load_dotenv(".env")
config_env = os.environ["FLASK_ENV"]
flask_app = create_app(config_env)
celery = flask_app.extensions["celery"]
