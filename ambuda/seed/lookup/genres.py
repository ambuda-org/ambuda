import logging

import ambuda.database as db
from ambuda.enums import TextGenre
from ambuda.seed.utils.data_utils import create_db
from sqlalchemy.orm import Session


def run(engine=None):
    """Create roles iff they don't exist already.

    NOTE: this script doesn't delete existing roles.
    """

    engine = engine or create_db()
    with Session(engine) as session:
        genres = session.query(db.Genre).all()
        existing_names = {s.name for s in genres}
        new_names = {r.value for r in TextGenre if r.value not in existing_names}

        if new_names:
            for name in new_names:
                status = db.Genre(name=name)
                session.add(status)
                logging.debug(f"Created genre: {name}")
            session.commit()

    logging.debug("Done. The following genres are defined:")
    with Session(engine) as session:
        for g in session.query(db.Genre).all():
            logging.debug(f"- {g.name}")


if __name__ == "__main__":
    run()
