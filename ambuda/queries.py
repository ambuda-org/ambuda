from sqlalchemy import create_engine
from sqlalchemy.orm import Session, selectinload, defer
from sqlalchemy.sql import *

import ambuda.database as db


engine = create_engine(db.DATABASE_URI, echo=True)
# TODO: session scoping
session = Session(engine)


def text(slug: str) -> list[db.Text]:
    return (
        session.query(db.Text)
        .filter(db.Text.slug == slug)
        .options(
            selectinload(db.Text.sections).load_only(
                db.TextSection.slug,
                db.TextSection.title,
            )
        )
        .first()
    )


def texts() -> list[db.Text]:
    return session.query(db.Text).all()


def select_mw(version: str, key: str):
    # TODO: restrict to MW only
    return session.query(db.DictionaryEntry).where(db.DictionaryEntry.key == key).all()
