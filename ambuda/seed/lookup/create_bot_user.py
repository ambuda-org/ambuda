import os

from sqlalchemy.orm import Session

from ambuda import consts
from ambuda import database as db
from ambuda.seed.utils.itihasa_utils import create_db

import logging


def _create_bot_user(session):
    try:
        password = os.environ["AMBUDA_BOT_PASSWORD"]
    except KeyError:
        raise ValueError("Please set the AMBUDA_BOT_PASSWORD environment variable.")

    user = db.User(username=consts.BOT_USERNAME, email="bot@ambuda.org")
    user.set_password(password)
    session.add(user)
    session.commit()


def run():
    """Create page statuses iff they don't exist already."""
    engine = create_db()
    logging.debug("Creating bot user ...")
    with Session(engine) as session:
        user = session.query(db.User).filter_by(username=consts.BOT_USERNAME).first()
        if not user:
            _create_bot_user(session)
    logging.debug("Done.")


if __name__ == "__main__":
    run()
