from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text as Text_,
)
from sqlalchemy.orm import relationship

from ambuda.models.base import Base, pk, foreign_key, same_as


def string():
    """Create a non-nullable string column that defaults to the empty string."""
    return Column(String, nullable=False, default="")


def text():
    return Column(Text_, nullable=False, default="")


class Project(Base):

    """A proofreading project. Each project has exactly one book."""

    __tablename__ = "proof_projects"

    #: Primary key.
    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, unique=True, nullable=False)
    #: Human-readable title, which we show on the page.
    title = Column(String, nullable=False)

    #: The document's author.
    author = string()
    #: The document's editor.
    editor = string()
    #: The document's publisher.
    publisher = string()
    #: The document's publication year.
    publication_year = string()

    #: Markdown for this project (to entice contributors, etc.)
    description = text()
    #: Defines page numbers (e.g. "x", "vii", ...)
    page_numbers = text()

    #: Timestamp at which this project was created.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: Timestamp at which this project was last updated.
    updated_at = Column(DateTime, default=same_as("created_at"), nullable=False)

    #: Discussion board for this project.
    board_id = foreign_key("discussion_boards.id")
    #: Creator of this project.
    #: FIXME: make non-nullable once we manually migrate the production setup.
    creator_id = Column(Integer, ForeignKey("users.id"), index=True)

    board = relationship("Board", cascade="delete")

    #: An ordered list of pages belonging to this project.
    pages = relationship(
        "Page", order_by=lambda: Page.order, backref="project", cascade="delete"
    )


class Page(Base):

    """A page in a proofreading project.

    This corresponds to a specific page in a PDF."""

    __tablename__ = "proof_pages"

    #: Primary key.
    id = pk()
    #: The project that owns this page.
    project_id = foreign_key("proof_projects.id")
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, index=True, nullable=False)
    #: (internal-only) A comes before B iff A.order < B.order.
    order = Column(Integer, nullable=False)
    #: (internal-only) used only so that we can implement optimistic locking
    #: for edit conflicts. See the `add_revision` function for details.
    version = Column(Integer, default=0, nullable=False)

    #: Page status
    status_id = Column(
        Integer, ForeignKey("proof_page_statuses.id"), index=True, nullable=False
    )
    status = relationship("PageStatus", backref="pages")

    #: An ordered list of revisions for this page (oldest first).
    revisions = relationship(
        "Revision",
        order_by=lambda: Revision.created,
        backref="page",
        cascade="delete",
    )


class PageStatus(Base):

    """The transcription status of a given page.

    For specific values, see `ambuda.seed.lookup.page_status`.
    """

    __tablename__ = "proof_page_statuses"

    #: Primary key.
    id = pk()
    #: Short human-readable label for this status.
    name = Column(String, nullable=False, unique=True)


class Revision(Base):

    """A specific page revision.

    To get the latest revision, sort by `created`.
    """

    __tablename__ = "proof_revisions"

    #: Primary key.
    id = pk()
    #: The project that owns this revision.
    project_id = foreign_key("proof_projects.id")
    #: The page this revision corresponds to.
    page_id = foreign_key("proof_pages.id")
    #: The author of this revision.
    author_id = foreign_key("users.id")
    #: Page status
    status_id = Column(
        Integer, ForeignKey("proof_page_statuses.id"), index=True, nullable=False
    )
    #: Timestamp at which this revision was created.
    #: FIXME: rename to `created_at` for consistency with other models.
    created = Column(DateTime, default=datetime.utcnow, nullable=False)
    #: An optional editor summary for this revision.
    summary = Column(Text_, nullable=False, default="")
    #: The actual content of this revision.
    content = Column(Text_, nullable=False)

    #: An ordered list of revisions for this page (newest first).
    author = relationship("User", backref="revisions")
    #: The project this revision belongs to.
    project = relationship("Project")
    #: The status of this page.
    status = relationship("PageStatus", backref="revisions")
