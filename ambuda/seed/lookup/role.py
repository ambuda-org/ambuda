import logging

from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.enums import SiteRole
from ambuda.seed.utils.data_utils import create_db


def run():
    """Create roles iff they don't exist already.

    NOTE: this script doesn't delete existing roles.
    """

    engine = create_db()
    with Session(engine) as session:
        roles = session.query(db.Role).all()
        existing_names = {s.name for s in roles}
        new_names = {r.value for r in SiteRole if r.value not in existing_names}

        if new_names:
            for name in new_names:
                status = db.Role(name=name)
                session.add(status)
                logging.debug(f"Created role: {name}")
            session.commit()

    logging.debug("Done. The following roles are defined:")
    with Session(engine) as session:
        for r in session.query(db.Role).all():
            logging.debug(f"- {r.name}")


if __name__ == "__main__":
    run()
