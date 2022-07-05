from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text as _Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from ambuda.models.base import Base, pk, foreign_key


class Project(Base):

    """A proofreading project. Each project has exactly one book."""

    __tablename__ = "proof_projects"

    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, unique=True, nullable=False)
    #: Human-readable title, which we show on the page.
    title = Column(String, nullable=False)

    pages = relationship(
        "Page", order_by=lambda: Page.order, backref="project", cascade="delete"
    )


class Page(Base):

    """A page in a proofreading project.

    This corresponds to a specific page in a PDF."""

    __tablename__ = "proof_pages"

    id = pk()
    #: The project that owns this page.
    project_id = foreign_key("proof_projects.id")
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, index=True, nullable=False)
    #: Filepath corresponding to this image.
    image_path = Column(String, nullable=False)
    #: (internal-only) A comes before B iff A.order < B.order.
    order = Column(Integer, nullable=False)
    #: (internal-only) used only so that we can implement optimistic locking
    #: for edit conflicts. See the `add_revision` function for details.
    version = Column(Integer, default=0)

    revisions = relationship(
        "Revision",
        order_by=lambda: Revision.created.desc(),
        backref="page",
        cascade="delete",
    )


class Revision(Base):

    """A specific page revision.

    To get the latest revision, sort by `created`.
    """

    __tablename__ = "proof_revisions"

    id = pk()
    #: The project that owns this revision.
    project_id = foreign_key("proof_projects.id")
    #: The page this revision corresponds to.
    page_id = foreign_key("proof_pages.id")
    #: The author of this revision.
    author_id = foreign_key("users.id")
    #: Timestamp at which this revision was created.
    created = Column(DateTime, default=datetime.utcnow)
    #: The actual content of this revision.
    content = Column(_Text, nullable=False)
