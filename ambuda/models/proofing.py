"""Models related to our proofing work."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy import Text as Text_
from sqlalchemy.orm import relationship

from ambuda.models.base import db, foreign_key, pk, same_as


def string():
    """Create a non-nullable string column that defaults to the empty string."""
    return Column(String, nullable=False, default="")


def text():
    """Create a non-nullable text column that defaults to the empty string."""
    return Column(Text_, nullable=False, default="")


class Project(db.Model):

    """A proofreading project.

    Each project corresponds to exactly one printed book.
    """

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

    creator = relationship("User")
    board = relationship("Board", cascade="delete")

    #: An ordered list of pages belonging to this project.
    pages = relationship(
        "Page", order_by=lambda: Page.order, backref="project", cascade="delete"
    )


class Page(db.Model):

    """A page in a proofreading project.

    This corresponds to a specific page in a PDF.
    """

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

    #: A raw-ish version of the Google OCR response. We store the response as a
    #: list of word-level bounding boxes in the following format:
    #:
    #:     x1 y1 x2 y2 text
    #:
    #: The field is nullable so that we can distinguish between (1) a page that
    #: has no OCR data and (2) a page whose OCR results are empty, such as if
    #: the page is blank.
    ocr_bounding_boxes = Column(Text_, nullable=True)

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


class PageStatus(db.Model):

    """The transcription status of a given page.

    For specific values, see `ambuda.seed.lookup.page_status`.
    """

    __tablename__ = "proof_page_statuses"

    #: Primary key.
    id = pk()
    #: Short human-readable label for this status.
    name = Column(String, nullable=False, unique=True)


class Revision(db.Model):

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
