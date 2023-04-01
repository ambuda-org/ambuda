"""Entrypoint for our Celery runner.
"""


import os

from dotenv import load_dotenv

from ambuda import create_app

# Celery runs various background tasks (PDF parsing, OCR) and needs access to
# our Flask application so that it has the right database context. Per the
# Flask docs [1], the right way to do this is to follow the pattern below.
#
# [1]: https://flask.palletsprojects.com/en/2.2.x/patterns/celery/
load_dotenv(".env")
config_env = os.environ["FLASK_ENV"]
flask_app = create_app(config_env)
celery = flask_app.extensions["celery"]
