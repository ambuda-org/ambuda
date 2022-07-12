import functools
from typing import Optional

from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import (
    Session,
    load_only,
    selectinload,
    scoped_session,
    sessionmaker,
)

import ambuda.database as db


# NOTE: this logic is copied from Flask-SQLAlchemy. We avoid Flask-SQLAlchemy
# because we also need to access the database from a non-Flask context when
# we run database seed scripts.
# ~~~
# Scope the session to the current greenlet if greenlet is available,
# otherwise fall back to the current thread.
try:
    from greenlet import getcurrent as _ident_func
except ImportError:
    from threading import get_ident as _ident_func


@functools.cache
def get_engine():
    # Wrapped call so that we read database URI from app config.

    # TODO: investigate better setup here
    # https://flask.palletsprojects.com/en/2.1.x/patterns/sqlalchemy/
    # https://stackoverflow.com/questions/12223335
    database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return create_engine(database_uri)


@functools.cache
def get_session_class():
    # Scoped sessions remove various kinds of errors, e.g. when using database
    # objects created on different threads.
    session_factory = sessionmaker(bind=get_engine())
    return scoped_session(session_factory, scopefunc=_ident_func)


def get_session():
    Session = get_session_class()
    return Session()


def texts() -> list[db.Text]:
    session = get_session()
    return session.query(db.Text).all()


def text(slug: str) -> db.Text:
    session = get_session()
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
    session = get_session()
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
    session = get_session()
    return session.query(db.TextSection).filter_by(text_id=text_id, slug=slug).first()


def block(text_id: int, slug) -> db.TextBlock:
    session = get_session()
    return session.query(db.TextBlock).filter_by(text_id=text_id, slug=slug).first()


def block_parse(block_id: int) -> list[db.BlockParse]:
    session = get_session()
    return session.query(db.BlockParse).filter_by(block_id=block_id).first()


def dictionaries() -> dict[str, db.Dictionary]:
    session = get_session()
    return {d.slug: d for d in session.query(db.Dictionary).all()}


def dict_entry(version: str, key: str) -> list[db.DictionaryEntry]:
    # TODO: same performance as dict_entries? If so, merge
    session = get_session()
    dicts = dictionaries()
    d = dicts[version]
    return (
        session.query(db.DictionaryEntry).filter_by(dictionary_id=d.id, key=key).all()
    )


def dict_entries(version: str, keys: list[str]) -> list[db.DictionaryEntry]:
    session = get_session()
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


def projects() -> list[db.Project]:
    session = get_session()
    return session.query(db.Project).all()


def project(slug) -> db.Project:
    session = get_session()
    return session.query(db.Project).filter(db.Project.slug == slug).first()


def create_project(*, title: str, slug: str):
    session = get_session()
    project = db.Project(slug=slug, title=title)

    session.add(project)
    session.commit()


def page(project_id, page_slug: str) -> db.Project:
    session = get_session()
    return (
        session.query(db.Page)
        .filter((db.Page.project_id == project_id) & (db.Page.slug == page_slug))
        .first()
    )


def user(username: str) -> Optional[db.User]:
    session = get_session()
    return session.query(db.User).filter_by(username=username).first()


def create_user(*, username: str, email: str, raw_password: str):
    session = get_session()
    user = db.User(username=username, email=email)
    user.set_password(raw_password)

    session.add(user)
    session.commit()
    return user
