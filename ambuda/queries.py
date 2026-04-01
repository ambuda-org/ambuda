"""Common queries.

We use this module to organize repetitive query logic and keep our views readable.
For simple or adhoc queries, you can just write them in their corresponding view.
"""

import dataclasses as dc
import functools

from flask import current_app
from sqlalchemy import case, create_engine, func, select
from sqlalchemy.orm import (
    load_only,
    scoped_session,
    selectinload,
    sessionmaker,
    Session,
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


# functools.cache makes this return value a singleton.
@functools.cache
def get_engine():
    database_uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    # For debugging, add echo=True to the constructor.
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


class Query:
    def __init__(self, session=None):
        self.session = session or get_session()

    def texts(self) -> list[db.Text]:
        stmt = select(db.Text).options(
            selectinload(db.Text.collections),
            selectinload(db.Text.alternate_titles),
        )
        return list(self.session.scalars(stmt).all())

    def page_statuses(self) -> list[db.PageStatus]:
        return list(self.session.scalars(select(db.PageStatus)).all())

    def text(self, slug: str) -> db.Text | None:
        stmt = (
            select(db.Text)
            .filter_by(slug=slug)
            .options(
                selectinload(db.Text.sections).load_only(
                    db.TextSection.slug,
                    db.TextSection.title,
                ),
                selectinload(db.Text.alternate_titles),
            )
        )
        return self.session.scalars(stmt).first()

    def text_meta(self, slug: str) -> db.Text | None:
        # TODO: is this method even useful? Is there a performance penalty for
        # using just `text`?
        stmt = (
            select(db.Text)
            .filter_by(slug=slug)
            .options(
                load_only(
                    db.Text.id,
                    db.Text.slug,
                )
            )
        )
        return self.session.scalars(stmt).first()

    def text_section(self, text_id: int, slug: str) -> db.TextSection | None:
        stmt = select(db.TextSection).filter_by(text_id=text_id, slug=slug)
        return self.session.scalars(stmt).first()

    def text_export(self, slug: str) -> db.TextExport | None:
        stmt = select(db.TextExport).filter_by(slug=slug)
        return self.session.scalars(stmt).first()

    def text_report(self, text_id: int) -> db.TextReport | None:
        stmt = (
            select(db.TextReport)
            .filter_by(text_id=text_id)
            .order_by(db.TextReport.created_at.desc())
        )
        return self.session.scalars(stmt).first()

    def text_report_summary(self, text_id: int) -> dict | None:
        """Fetch just the summary JSON for a text report (avoids loading the full payload)."""
        stmt = (
            select(db.TextReport.summary)
            .filter_by(text_id=text_id)
            .order_by(db.TextReport.created_at.desc())
        )
        return self.session.scalar(stmt)

    def block(self, text_id: int, slug: str) -> db.TextBlock | None:
        stmt = select(db.TextBlock).filter_by(text_id=text_id, slug=slug)
        return self.session.scalars(stmt).first()

    def block_parse(self, block_id: int) -> db.BlockParse | None:
        stmt = select(db.BlockParse).filter_by(block_id=block_id)
        return self.session.scalars(stmt).first()

    def dictionaries(self) -> list[db.Dictionary]:
        return list(self.session.scalars(select(db.Dictionary)).all())

    def dict_entries(
        self, sources: list[str], keys: list[str]
    ) -> dict[str, list[db.DictionaryEntry]]:
        dicts = self.dictionaries()
        source_ids = [d.id for d in dicts if d.slug in sources]

        stmt = select(db.DictionaryEntry).filter(
            (db.DictionaryEntry.dictionary_id.in_(source_ids))
            & (db.DictionaryEntry.key.in_(keys))
        )
        rows = list(self.session.scalars(stmt).all())

        dict_id_to_slug = {d.id: d.slug for d in dicts}
        mapping = {s: [] for s in sources}
        for row in rows:
            dict_slug = dict_id_to_slug[row.dictionary_id]
            mapping[dict_slug].append(row)
        return mapping

    def active_projects(self) -> list[db.Project]:
        from ambuda.models.proofing import ProjectStatus

        stmt = select(db.Project).filter(db.Project.status == ProjectStatus.ACTIVE)
        return list(self.session.scalars(stmt).all())

    def pending_projects(self) -> list[db.Project]:
        from ambuda.models.proofing import ProjectStatus

        stmt = select(db.Project).filter(db.Project.status == ProjectStatus.PENDING)
        return list(self.session.scalars(stmt).all())

    def paginated_projects(
        self,
        statuses: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
        sort_field: str = "title",
        sort_dir: str = "asc",
        search: str = "",
        genre_ids: list[int] | None = None,
        tag_id: int | None = None,
    ) -> tuple[list[db.Project], int]:
        from ambuda.models.proofing import ProjectStatus, project_tag_association

        status_map = {
            "active": ProjectStatus.ACTIVE,
            "pending": ProjectStatus.PENDING,
            "closed-copy": ProjectStatus.CLOSED_COPYRIGHT,
            "closed-duplicate": ProjectStatus.CLOSED_DUPLICATE,
            "closed-quality": ProjectStatus.CLOSED_QUALITY,
        }

        base = select(db.Project)
        if statuses:
            enum_values = [status_map[s] for s in statuses if s in status_map]
            if enum_values:
                base = base.filter(db.Project.status.in_(enum_values))

        if search:
            like = f"%{search}%"
            base = base.filter(
                db.Project.display_title.ilike(like)
                | db.Project.description.ilike(like)
            )

        if genre_ids:
            base = base.filter(db.Project.genre_id.in_(genre_ids))

        if tag_id:
            base = base.join(project_tag_association).filter(
                project_tag_association.c.tag_id == tag_id
            )

        count_stmt = select(func.count()).select_from(base.subquery())
        total = self.session.scalar(count_stmt) or 0

        sort_map = {
            "title": db.Project.display_title,
            "created": db.Project.created_at,
        }
        sort_col = sort_map.get(sort_field, db.Project.display_title)
        if sort_dir == "desc":
            sort_col = sort_col.desc()

        load_opts = load_only(
            db.Project.id,
            db.Project.display_title,
            db.Project.slug,
            db.Project.created_at,
            db.Project.description,
            db.Project.genre_id,
        )

        stmt = (
            base.options(
                load_opts,
                selectinload(db.Project.genre),
                selectinload(db.Project.tags),
            )
            .order_by(sort_col)
            .limit(per_page)
            .offset((page - 1) * per_page)
        )

        projects = list(self.session.scalars(stmt).all())
        return projects, total

    def project_tags(self) -> list[db.ProjectTag]:
        return list(
            self.session.scalars(
                select(db.ProjectTag).order_by(db.ProjectTag.name)
            ).all()
        )

    def user_recent_projects(self, user_id: int, limit: int = 5) -> list[db.Project]:
        stmt = (
            select(db.Project)
            .join(db.Revision, db.Revision.project_id == db.Project.id)
            .filter(db.Revision.author_id == user_id)
            .group_by(db.Project.id)
            .order_by(func.max(db.Revision.created_at).desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def needs_help_projects(self, limit: int = 5) -> list[db.Project]:
        from ambuda.models.proofing import ProjectStatus

        r0_status = self.session.scalars(
            select(db.PageStatus).filter(db.PageStatus.name == "reviewed-0")
        ).first()
        if not r0_status:
            return []

        total_pages = func.count(db.Page.id)
        r0_pages = func.count(case((db.Page.status_id == r0_status.id, db.Page.id)))

        stmt = (
            select(db.Project)
            .join(db.Page, db.Page.project_id == db.Project.id)
            .filter(db.Project.status == ProjectStatus.ACTIVE)
            .group_by(db.Project.id)
            .having(total_pages > 0)
            .order_by((r0_pages * 1.0 / total_pages).desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def project(self, slug: str) -> db.Project | None:
        stmt = select(db.Project).filter(db.Project.slug == slug)
        return self.session.scalars(stmt).first()

    def thread(self, *, id: int) -> db.Thread | None:
        stmt = select(db.Thread).filter_by(id=id)
        return self.session.scalars(stmt).first()

    def post(self, *, id: int) -> db.Post | None:
        stmt = select(db.Post).filter_by(id=id)
        return self.session.scalars(stmt).first()

    def create_thread(self, *, board_id: int, user_id: int, title: str, content: str):
        assert board_id
        thread = db.Thread(board_id=board_id, author_id=user_id, title=title)
        self.session.add(thread)
        self.session.flush()

        post = db.Post(
            board_id=board_id, author_id=user_id, thread_id=thread.id, content=content
        )
        self.session.add(post)
        self.session.commit()

    def create_post(
        self, *, board_id: int, thread: db.Thread, user_id: int, content: str
    ):
        post = db.Post(
            board_id=board_id, author_id=user_id, thread_id=thread.id, content=content
        )
        self.session.add(post)
        self.session.flush()

        assert post.created_at
        thread.updated_at = post.created_at
        self.session.add(thread)
        self.session.commit()

    def pages_with_revisions(self, project_id, page_slugs: list[str]) -> list[db.Page]:
        stmt = (
            select(db.Page)
            .filter((db.Page.project_id == project_id) & (db.Page.slug.in_(page_slugs)))
            .options(selectinload(db.Page.revisions))
        )
        return list(self.session.scalars(stmt).all())

    def page(self, project_id, page_slug: str) -> db.Page | None:
        stmt = select(db.Page).filter(
            (db.Page.project_id == project_id) & (db.Page.slug == page_slug)
        )
        return self.session.scalars(stmt).first()

    def revision(self, revision_id) -> db.Revision | None:
        stmt = select(db.Revision).filter((db.Revision.id == revision_id))
        return self.session.scalars(stmt).first()

    def user(self, username: str) -> db.User | None:
        stmt = select(db.User).filter_by(
            username=username, is_deleted=False, is_banned=False
        )
        return self.session.scalars(stmt).first()

    def create_user(self, *, username: str, email: str, raw_password: str) -> db.User:
        user = db.User(username=username, email=email)
        user.set_password(raw_password)
        self.session.add(user)
        self.session.commit()
        return user

    def blog_post(self, slug: str) -> db.BlogPost | None:
        stmt = select(db.BlogPost).filter_by(slug=slug)
        return self.session.scalars(stmt).first()

    def blog_posts(self) -> list[db.BlogPost]:
        stmt = select(db.BlogPost).order_by(db.BlogPost.created_at.desc())
        return list(self.session.scalars(stmt).all())

    def site_config(self) -> db.SiteConfig | None:
        return self.session.scalars(select(db.SiteConfig)).first()

    def project_sponsorships(self) -> list[db.ProjectSponsorship]:
        results = list(self.session.scalars(select(db.ProjectSponsorship)).all())
        return sorted(results, key=lambda s: s.sa_title or s.en_title)

    def contributor_info(self) -> list[db.ContributorInfo]:
        stmt = select(db.ContributorInfo).order_by(db.ContributorInfo.name)
        return list(self.session.scalars(stmt).all())

    def genres(self) -> list[db.Genre]:
        return list(self.session.scalars(select(db.Genre)).all())

    def author(self, slug: str) -> db.Author | None:
        stmt = select(db.Author).filter_by(slug=slug)
        return self.session.scalars(stmt).first()

    def authors(self) -> list[db.Author]:
        return list(self.session.scalars(select(db.Author)).all())

    def all_collections(self) -> list[db.TextCollection]:
        """Fetch all collections in one query, ordered by order."""
        stmt = select(db.TextCollection).order_by(db.TextCollection.order)
        return list(self.session.scalars(stmt).all())

    def collections(self) -> list[db.TextCollection]:
        """Return top-level collections with children assembled in Python."""
        all_colls = self.all_collections()
        by_parent = group_collections_by_parent(all_colls)
        # Wire up children so lazy loads aren't triggered
        from sqlalchemy.orm.attributes import set_committed_value

        for c in all_colls:
            set_committed_value(c, "children", by_parent.get(c.id, []))
        return by_parent.get(None, [])

    def collection(self, slug: str) -> db.TextCollection | None:
        stmt = select(db.TextCollection).filter_by(slug=slug)
        return self.session.scalars(stmt).first()

    def collection_texts(self, collection: db.TextCollection) -> list[db.Text]:
        descendant_ids = all_descendant_ids(collection.id, self.all_collections())
        stmt = (
            select(db.Text)
            .join(db.text_collection_association)
            .filter(db.text_collection_association.c.collection_id.in_(descendant_ids))
            .order_by(db.Text.title)
        )
        return list(self.session.scalars(stmt).all())


def group_collections_by_parent(
    all_collections: list[db.TextCollection],
) -> dict[int | None, list[db.TextCollection]]:
    """Group a flat list of collections by parent_id."""
    by_parent: dict[int | None, list[db.TextCollection]] = {}
    for c in all_collections:
        by_parent.setdefault(c.parent_id, []).append(c)
    return by_parent


def all_descendant_ids(
    collection_id: int, all_collections: list[db.TextCollection]
) -> list[int]:
    """Return IDs of a collection and all its descendants, using a flat list."""
    by_parent = group_collections_by_parent(all_collections)
    ids = []
    stack = [collection_id]
    while stack:
        cid = stack.pop()
        ids.append(cid)
        for child in by_parent.get(cid, []):
            stack.append(child.id)
    return ids


def texts() -> list[db.Text]:
    """Return a list of all texts in no particular older."""
    query = Query(get_session())
    return query.texts()


def page_statuses() -> list[db.PageStatus]:
    query = Query(get_session())
    return query.page_statuses()


def text(slug: str) -> db.Text | None:
    query = Query(get_session())
    return query.text(slug)


def text_meta(slug: str) -> db.Text | None:
    """Return only specific fields from the given text."""
    # TODO: is this method even useful? Is there a performance penalty for
    # using just `text`?
    query = Query(get_session())
    return query.text_meta(slug)


def text_section(text_id: int, slug: str) -> db.TextSection | None:
    query = Query(get_session())
    return query.text_section(text_id, slug)


def text_export(slug: str) -> db.TextExport | None:
    query = Query(get_session())
    return query.text_export(slug)


def text_report(text_id: int) -> db.TextReport | None:
    query = Query(get_session())
    return query.text_report(text_id)


def text_report_summary(text_id: int) -> dict | None:
    query = Query(get_session())
    return query.text_report_summary(text_id)


def block(text_id: int, slug: str) -> db.TextBlock | None:
    query = Query(get_session())
    return query.block(text_id, slug)


def block_parse(block_id: int) -> db.BlockParse | None:
    query = Query(get_session())
    return query.block_parse(block_id)


def dictionaries() -> list[db.Dictionary]:
    query = Query(get_session())
    return query.dictionaries()


def dict_entries(
    sources: list[str], keys: list[str]
) -> dict[str, list[db.DictionaryEntry]]:
    """
    :param sources: slugs of the dictionaries to query
    :param keys: the keys (dictionary entries) to query
    """
    query = Query(get_session())
    return query.dict_entries(sources, keys)


def active_projects() -> list[db.Project]:
    """Return all active projects in no particular order."""
    query = Query(get_session())
    return query.active_projects()


def pending_projects() -> list[db.Project]:
    """Return all pending projects in no particular order."""
    query = Query(get_session())
    return query.pending_projects()


def paginated_projects(**kwargs) -> tuple[list[db.Project], int]:
    query = Query(get_session())
    return query.paginated_projects(**kwargs)


def project_tags() -> list[db.ProjectTag]:
    query = Query(get_session())
    return query.project_tags()


def user_recent_projects(user_id: int, limit: int = 5) -> list[db.Project]:
    query = Query(get_session())
    return query.user_recent_projects(user_id, limit)


def needs_help_projects(limit: int = 5) -> list[db.Project]:
    query = Query(get_session())
    return query.needs_help_projects(limit)


def project(slug: str) -> db.Project | None:
    query = Query(get_session())
    return query.project(slug)


def thread(*, id: int) -> db.Thread | None:
    query = Query(get_session())
    return query.thread(id=id)


def post(*, id: int) -> db.Post | None:
    query = Query(get_session())
    return query.post(id=id)


def create_thread(*, board_id: int, user_id: int, title: str, content: str):
    query = Query(get_session())
    return query.create_thread(
        board_id=board_id, user_id=user_id, title=title, content=content
    )


def create_post(*, board_id: int, thread: db.Thread, user_id: int, content: str):
    query = Query(get_session())
    return query.create_post(
        board_id=board_id, thread=thread, user_id=user_id, content=content
    )


def pages_with_revisions(project_id, page_slugs: list[str]) -> list[db.Page]:
    query = Query(get_session())
    return query.pages_with_revisions(project_id, page_slugs)


def page(project_id, page_slug: str) -> db.Page | None:
    query = Query(get_session())
    return query.page(project_id, page_slug)


def revision(revision_id) -> db.Revision | None:
    query = Query(get_session())
    return query.revision(revision_id)


def user(username: str) -> db.User | None:
    query = Query(get_session())
    return query.user(username)


def create_user(*, username: str, email: str, raw_password: str) -> db.User:
    query = Query(get_session())
    return query.create_user(username=username, email=email, raw_password=raw_password)


def blog_post(slug: str) -> db.BlogPost | None:
    """Fetch the given blog post."""
    query = Query(get_session())
    return query.blog_post(slug)


def blog_posts() -> list[db.BlogPost]:
    """Fetch all blog posts."""
    query = Query(get_session())
    return query.blog_posts()


def site_config():
    """Fetch the singleton site config, or return defaults."""
    from ambuda.models.site import SiteConfigData

    query = Query(get_session())
    row = query.site_config()
    if row:
        return row.parsed()
    return SiteConfigData()


def project_sponsorships() -> list[db.ProjectSponsorship]:
    query = Query(get_session())
    return query.project_sponsorships()


def contributor_info() -> list[db.ContributorInfo]:
    query = Query(get_session())
    return query.contributor_info()


def genres() -> list[db.Genre]:
    query = Query(get_session())
    return query.genres()


def author(slug: str) -> db.Author | None:
    query = Query(get_session())
    return query.author(slug)


def authors() -> list[db.Author]:
    query = Query(get_session())
    return query.authors()


def collections() -> list[db.TextCollection]:
    query = Query(get_session())
    return query.collections()


def collection(slug: str) -> db.TextCollection | None:
    query = Query(get_session())
    return query.collection(slug)


def collection_texts(collection_: db.TextCollection) -> list[db.Text]:
    query = Query(get_session())
    return query.collection_texts(collection_)
