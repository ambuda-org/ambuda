"""Common queries.

We use this module to organize repetitive query logic and keep our views readable.
For simple or adhoc queries, you can just write them in their corresponding view.
"""


from flask import current_app
from sqlalchemy.orm import load_only, selectinload

import ambuda.database as db
from ambuda.models.base import db as flask_sqla


def get_session():
    with current_app.app_context():
        return flask_sqla.session


def texts() -> list[db.Text]:
    """Return a list of all texts in no particular older."""
    session = get_session()
    return session.query(db.Text).all()


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
