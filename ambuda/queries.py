"""Common queries.

We use this module to organize repetitive query logic and keep our views readable.
For simple or adhoc queries, you can just write them in their corresponding view.
"""

import functools

from flask import current_app
from sqlalchemy import create_engine
from sqlalchemy.orm import load_only, scoped_session, selectinload, sessionmaker

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


# functools.cache makes this return value a singleton.
@functools.cache
def get_engine():
    database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    return create_engine(database_uri)


# functools.cache makes this return value a singleton.
@functools.cache
def get_session_class():
    # Scoped sessions remove various kinds of errors, e.g. when using database
    # objects created on different threads.
    #
    # For details, see:
    # - https://stackoverflow.com/questions/12223335
    # - https://flask.palletsprojects.com/en/2.1.x/patterns/sqlalchemy/
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return scoped_session(session_factory, scopefunc=_ident_func)


def get_session():
    """Instantiate a scoped session.

    If we implemented this right, there should be exactly one unique session
    per request.
    """
    Session = get_session_class()
    return Session()


def texts() -> list[db.Text]:
    """Return a list of all texts in no particular older."""
    session = get_session()
    return session.query(db.Text).all()


def texts_genre(genre=None) -> list[str]:
    """Return a list of all texts in a genre."""
    session = get_session()
    query = session.query(db.Text.slug).join(db.Genre)  # Join the Text and Genre tables
    if genre:
        query = query.filter(db.Genre.name == genre.name)  # Filter by genre name
    texts = query.all()
    return [text[0] for text in texts]


def page_statuses() -> list[db.PageStatus]:
    session = get_session()
    return session.query(db.PageStatus).all()


def text(slug: str) -> db.Text | None:
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
    """Return only specific fields from the given text."""
    # TODO: is this method even useful? Is there a performance penalty for
    # using just `text`?
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


def text_section(text_id: int, slug: str) -> db.TextSection | None:
    session = get_session()
    return session.query(db.TextSection).filter_by(text_id=text_id, slug=slug).first()


def block(text_id: int, slug: str) -> db.TextBlock | None:
    session = get_session()
    return session.query(db.TextBlock).filter_by(text_id=text_id, slug=slug).first()


def block_parse(block_id: int) -> db.BlockParse | None:
    session = get_session()
    return session.query(db.BlockParse).filter_by(block_id=block_id).first()


def dictionaries() -> list[db.Dictionary]:
    session = get_session()
    return session.query(db.Dictionary).all()


def dict_entries(
    sources: list[str], keys: list[str]
) -> dict[str, list[db.DictionaryEntry]]:
    """
    :param sources: slugs of the dictionaries to query
    :param keys: the keys (dictionary entries) to query
    """
    session = get_session()
    dicts = dictionaries()
    source_ids = [d.id for d in dicts if d.slug in sources]

    rows = (
        session.query(db.DictionaryEntry)
        .filter(
            (db.DictionaryEntry.dictionary_id.in_(source_ids))
            & (db.DictionaryEntry.key.in_(keys))
        )
        .all()
    )

    dict_id_to_slug = {d.id: d.slug for d in dicts}
    mapping = {s: [] for s in sources}
    for row in rows:
        dict_slug = dict_id_to_slug[row.dictionary_id]
        mapping[dict_slug].append(row)
    return mapping


def projects() -> list[db.Project]:
    """Return all projects in no particular order."""
    session = get_session()
    return session.query(db.Project).all()


def project(slug: str) -> db.Project | None:
    session = get_session()
    return session.query(db.Project).filter(db.Project.slug == slug).first()


def thread(*, id: int) -> db.Thread | None:
    session = get_session()
    return session.query(db.Thread).filter_by(id=id).first()


def post(*, id: int) -> db.Post | None:
    session = get_session()
    return session.query(db.Post).filter_by(id=id).first()


def create_thread(*, board_id: int, user_id: int, title: str, content: str):
    session = get_session()

    assert board_id
    thread = db.Thread(board_id=board_id, author_id=user_id, title=title)
    session.add(thread)
    session.flush()

    post = db.Post(
        board_id=board_id, author_id=user_id, thread_id=thread.id, content=content
    )
    session.add(post)
    session.commit()


def create_post(*, board_id: int, thread: db.Thread, user_id: int, content: str):
    session = get_session()
    post = db.Post(
        board_id=board_id, author_id=user_id, thread_id=thread.id, content=content
    )
    session.add(post)
    session.flush()

    assert post.created_at
    thread.updated_at = post.created_at
    session.add(thread)
    session.commit()


def page(project_id, page_slug: str) -> db.Page | None:
    session = get_session()
    return (
        session.query(db.Page)
        .filter((db.Page.project_id == project_id) & (db.Page.slug == page_slug))
        .first()
    )


def user(username: str) -> db.User | None:
    session = get_session()
    return (
        session.query(db.User)
        .filter_by(username=username, is_deleted=False, is_banned=False)
        .first()
    )


def create_user(*, username: str, email: str, raw_password: str) -> db.User:
    session = get_session()
    user = db.User(username=username, email=email)
    user.set_password(raw_password)
    session.add(user)
    session.flush()

    # Allow all users to be proofreaders
    proofreader_role = (
        session.query(db.Role).filter_by(name=db.SiteRole.P1.value).first()
    )
    user_role = db.UserRoles(user_id=user.id, role_id=proofreader_role.id)
    session.add(user_role)

    session.commit()
    return user


def blog_post(slug: str) -> db.BlogPost | None:
    """Fetch the given blog post."""
    session = get_session()
    return session.query(db.BlogPost).filter_by(slug=slug).first()


def blog_posts() -> list[db.BlogPost]:
    """Fetch all blog posts."""
    session = get_session()
    return session.query(db.BlogPost).order_by(db.BlogPost.created_at.desc()).all()


def project_sponsorships() -> list[db.ProjectSponsorship]:
    session = get_session()
    results = session.query(db.ProjectSponsorship).all()
    return sorted(results, key=lambda s: s.sa_title or s.en_title)


def contributor_info() -> list[db.ContributorInfo]:
    session = get_session()
    return session.query(db.ContributorInfo).order_by(db.ContributorInfo.name).all()


def genres() -> list[db.Genre]:
    session = get_session()
    return session.query(db.Genre).all()
