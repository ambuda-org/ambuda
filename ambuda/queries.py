import functools

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, load_only, selectinload

import ambuda.database as db


engine = create_engine(db.DATABASE_URI)
# TODO: session scoping
session = Session(engine)


def texts() -> list[db.Text]:
    return session.query(db.Text).all()


def text(slug: str) -> db.Text:
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


def text_meta(slug: str) -> db.Text:
    return (
        session.query(db.Text)
        .filter_by(slug=slug)
        .options(
            load_only(
                db.Text.id,
                db.Text.slug,
            )
        )
        .first()
    )


def text_section(text_id: int, slug: str) -> db.TextSection:
    return session.query(db.TextSection).filter_by(text_id=text_id, slug=slug).first()


def block_meta(text_id: int, slug) -> db.Text:
    return (
        session.query(db.TextBlock)
        .filter_by(text_id=text_id, slug=slug)
        .options(
            load_only(
                db.TextBlock.id,
                db.TextBlock.slug,
            )
        )
        .first()
    )


def block_parse(block_id: int) -> list[db.BlockParse]:
    return session.query(db.BlockParse).filter_by(block_id=block_id).first()


# TODO: maybe don't functool cache?
@functools.cache
def dictionaries() -> dict[str, db.Dictionary]:
    return {d.slug: d for d in session.query(db.Dictionary).all()}


def dict_entry(version: str, key: str) -> list[db.DictionaryEntry]:
    # TODO: same performance as dict_entries? If so, merge
    dicts = dictionaries()
    d = dicts[version]
    return (
        session.query(db.DictionaryEntry).filter_by(dictionary_id=d.id, key=key).all()
    )


def dict_entries(version: str, keys: list[str]) -> list[db.DictionaryEntry]:
    dicts = dictionaries()
    d = dicts[version]
    return (
        session.query(db.DictionaryEntry)
        .filter(
            (db.DictionaryEntry.dictionary_id == d.id)
            & (db.DictionaryEntry.key.in_(keys))
        )
        .all()
    )
