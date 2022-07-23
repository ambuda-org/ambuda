from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.seed.utils.itihasa_utils import create_db


FIELD_NAMES = [
    # Page has never been fully proofread.
    "reviewed-0",
    # Page has been fully proofread once.
    "reviewed-1",
    # Page has been fully proofread twice.
    "reviewed-2",
    # Page is out of scope for proofreading.
    "skip",
]


def log(*a):
    print(*a)


def get_default_id():
    """Used in the `add_page_statuses` migration."""
    engine = create_db()
    with Session(engine) as session:
        return session.query(db.PageStatus).filter_by(name="reviewed-0").one()


def run():
    """Create page statuses iff they don't exist already."""

    engine = create_db()
    log("Creating PageStatus rows ...")
    with Session(engine) as session:
        statuses = session.query(db.PageStatus).all()
        existing_names = {s.name for s in statuses}
        new_names = {n for n in FIELD_NAMES if n not in existing_names}

        if new_names:
            for name in new_names:
                status = db.PageStatus(name=name)
                session.add(status)
            session.commit()
    log("Done.")


if __name__ == "__main__":
    run()
