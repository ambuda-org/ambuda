import logging

from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.enums import SitePageStatus
from ambuda.seed.utils.itihasa_utils import create_db


def get_default_id():
    """Used in the `add_page_statuses` migration."""
    engine = create_db()
    with Session(engine) as session:
        return session.query(db.PageStatus).filter_by(name=SitePageStatus.R0).one()


def run():
    """Create page statuses iff they don't exist already."""
    engine = create_db()
    logging.debug("Creating PageStatus rows ...")
    with Session(engine) as session:
        statuses = session.query(db.PageStatus).all()
        existing_names = {s.name for s in statuses}
        new_names = {n.value for n in SitePageStatus if n not in existing_names}

        if new_names:
            for name in new_names:
                status = db.PageStatus(name=name)
                session.add(status)
            session.commit()
    logging.debug("Done.")


if __name__ == "__main__":
    run()
