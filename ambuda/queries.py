import functools

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, selectinload, defer
from sqlalchemy.sql import *

import ambuda.database as db


engine = create_engine(db.DATABASE_URI)
# TODO: session scoping
session = Session(engine)


def text(slug: str) -> list[db.Text]:
    return (
        session.query(db.Text)
        .filter_by(slug=slug)
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


# TODO: maybe don't functool cache?
@functools.cache
def dictionaries() -> list[db.Dictionary]:
    return session.query(db.Dictionary).all()


def select_mw(version: str, key: str):
    dicts = dictionaries()
    d = [d for d in dicts if d.slug == version][0]
    # TODO: restrict to MW only
    return (
        session.query(db.DictionaryEntry).filter_by(dictionary_id=d.id, key=key).all()
    )
