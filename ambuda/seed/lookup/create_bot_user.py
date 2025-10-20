import logging
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from ambuda import consts
from ambuda import database as db
from ambuda.seed.utils.data_utils import create_db


def _create_bot_user(session):
    try:
        password = os.environ["AMBUDA_BOT_PASSWORD"]
    except KeyError as e:
        raise ValueError(
            "Please set the AMBUDA_BOT_PASSWORD environment variable."
        ) from e

    user = db.User(username=consts.BOT_USERNAME, email="bot@ambuda.org")
    user.set_password(password)
    session.add(user)
    session.commit()


def run():
    """Create page statuses iff they don't exist already."""
    engine = create_db()
    logging.debug("Creating bot user ...")
    with Session(engine) as session:
        stmt = select(db.User).filter_by(username=consts.BOT_USERNAME)
        user = session.scalars(stmt).first()
        if not user:
            _create_bot_user(session)
    logging.debug("Done.")


if __name__ == "__main__":
    run()
