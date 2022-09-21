"""Initializes the development database by creating all tables.

This module is used in `scripts/initialize_from_scratch.sh`.

TODO: what are the implications of running `create_all` on app startup?
"""

from dotenv import load_dotenv
from sqlalchemy import create_engine

from ambuda import config
from ambuda import database as db

load_dotenv()


def run():
    conf = config.load_config_object("development")
    engine = create_engine(conf.SQLALCHEMY_DATABASE_URI)
    db.Base.metadata.create_all(engine)


if __name__ == "__main__":
    run()
