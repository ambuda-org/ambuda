"""Models related to our proofing work."""

import uuid
from datetime import datetime, UTC
from enum import StrEnum
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Table, event
from sqlalchemy import Text as Text_
from sqlalchemy.orm import relationship, Mapped, mapped_column

from ambuda.models.base import Base, foreign_key, pk, same_as
from ambuda.utils.s3 import S3Path


def string():
    """Create a non-nullable string column that defaults to the empty string."""
    return mapped_column(String, nullable=False, default="")


def text():
    """Create a non-nullable text column that defaults to the empty string."""
    return Column(Text_, nullable=False, default="")


def _create_uuid():
    return str(uuid.uuid4())


# Association table for many-to-many relationship between Project and ProjectTag
project_tag_association = Table(
    "project_tag_association",
    Base.metadata,
    Column("project_id", Integer, ForeignKey("proof_projects.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("project_tags.id"), primary_key=True),
)


class Genre(Base):
    """A text genre.

    We use genre to help people sort through different projects/texts and select the ones they
    care about.
    """

    __tablename__ = "genres"

    #: Primary key.
    id = pk()
    #: The name of this genre.
    name = Column(String, unique=True, nullable=False)

    def __str__(self):
        return self.name


class LanguageCode(StrEnum):
    """ISO 639 language codes relevant to Ambuda."""

    SA = "sa"  # Sanskrit
    EN = "en"  # English
    HI = "hi"  # Hindi
    TA = "ta"  # Tamil
    TE = "te"  # Telugu
    KN = "kn"  # Kannada
    ML = "ml"  # Malayalam
    MR = "mr"  # Marathi
    GU = "gu"  # Gujarati
    BN = "bn"  # Bengali
    PA = "pa"  # Punjabi
    OR = "or"  # Odia
    PI = "pi"  # Pali
    BO = "bo"  # Tibetan

    @property
    def label(self) -> str:
        return _LANGUAGE_LABELS[self.value]


_LANGUAGE_LABELS: dict[str, str] = {
    "sa": "Sanskrit",
    "en": "English",
    "hi": "Hindi",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "gu": "Gujarati",
    "bn": "Bengali",
    "pa": "Punjabi",
    "or": "Odia",
    "pi": "Pali",
    "bo": "Tibetan",
}


class PublishConfig(BaseModel):
    slug: str
    title: str
    target: str | None = None
    author: str | None = None
    genre: str | None = None
    language: LanguageCode = LanguageCode.SA
    parent_slug: str | None = None


class ProjectConfig(BaseModel):
    publish: list[PublishConfig] = Field(default_factory=list)
    pages: list[str] = Field(default_factory=list)


class ProjectStatus(StrEnum):
    """Describes the status of some project."""

    #: Generally available for editing.
    #:
    #: Ideally, this is the state most projects should have.
    ACTIVE = "active"
    #: Uploaded, but needs review before general availability.
    #:
    #: (Not called "in review" because all active projects are edited / "reviewed", so the name
    #: would be confusing.)
    PENDING = "pending"
    #: Closed due to a potential copyright conflict.
    CLOSED_COPYRIGHT = "closed-copy"
    #: Closed since the project duplicates another text, either on Ambuda or elsewhere.
    CLOSED_DUPLICATE = "closed-duplicate"
    #: Closed because the PDF is very low quality.
    CLOSED_QUALITY = "closed-quality"


class Project(Base):
    """A proofreading project.

    Each project corresponds to exactly one printed book.
    """

    __tablename__ = "proof_projects"

    #: Primary key.
    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    #: UUID (for s3 uploads, stability despite slug renames, etc.)
    uuid: Mapped[str] = mapped_column(unique=True, nullable=False, default=_create_uuid)

    #: Human-readable title, which we show on the page.
    display_title: Mapped[str] = mapped_column(String, nullable=False)

    #: The full book title as it appears in print.
    print_title: Mapped[str] = string()
    #: The document's author.
    author: Mapped[str] = string()
    #: The document's editor.
    editor: Mapped[str] = string()
    #: The document's publisher.
    publisher: Mapped[str] = string()
    #: The document's publication year.
    publication_year: Mapped[str] = string()
    #: A link to the book's WorldCat entry, if available.
    worldcat_link: Mapped[str] = string()
    #: The URL from which the source PDF was fetched, if any.
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)

    #: Markdown for this project (to entice contributors, etc.)
    description = text()
    #: Notes about the project, for internal and scholarly use.
    notes = text()
    #: Defines page numbers (e.g. "x", "vii", ...)
    page_numbers = text()
    #: Additional metadata for this project as a JSON document.
    #: The schema is defined in `ProjectConfig`.
    config = Column(JSON, nullable=True)
    #: The status of this project.
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=ProjectStatus.PENDING
    )

    #: Timestamp at which this project was created.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
    #: Timestamp at which this project was last updated.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=same_as("created_at"), nullable=False
    )

    #: Discussion board for this project.
    board_id = foreign_key("discussion_boards.id")
    #: Creator of this project.
    #: FIXME: make non-nullable once we manually migrate the production setup.
    creator_id = Column(Integer, ForeignKey("users.id"), index=True)
    #: The genre of this project.
    genre_id = Column(Integer, ForeignKey("genres.id"), index=True)

    creator = relationship("User")
    board = relationship("Board", cascade="delete")
    genre = relationship("Genre")

    #: An ordered list of pages belonging to this project.
    pages = relationship(
        "Page", order_by=lambda: Page.order, backref="project", cascade="delete"
    )
    #: Tags associated with this project.
    tags = relationship(
        "ProjectTag",
        secondary=project_tag_association,
        back_populates="projects",
    )
    sources = relationship("ProjectSource", back_populates="project", cascade="delete")

    def __str__(self):
        return self.slug

    def s3_path(self, bucket: str) -> S3Path:
        return S3Path(bucket=bucket, key=f"proofing/{self.uuid}/pdf/source.pdf")


class ProjectTag(Base):
    __tablename__ = "project_tags"

    id = pk()
    name: Mapped[str] = mapped_column(String, unique=True)

    #: Projects associated with this tag.
    projects = relationship(
        "Project",
        secondary=project_tag_association,
        back_populates="tags",
    )


class ProjectSource(Base):
    """A source reference for a proofing project."""

    __tablename__ = "project_sources"

    id = pk()
    project_id = foreign_key("proof_projects.id")
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
    author_id = Column(Integer, ForeignKey("users.id"), index=True)

    project = relationship("Project", back_populates="sources")
    author = relationship("User")


@event.listens_for(Project, "before_insert")
@event.listens_for(Project, "before_update")
def validate_config(mapper, connection, project):
    if project.config:
        try:
            ProjectConfig.model_validate_json(project.config)
        except Exception as e:
            raise ValueError(f"Project.config must be a valid JSON document: {e}")


@event.listens_for(Project, "before_insert")
@event.listens_for(Project, "before_update")
def validate_status(mapper, connection, project):
    if project.status:
        try:
            ProjectStatus(project.status)
        except ValueError:
            valid_values = ", ".join([s.value for s in ProjectStatus])
            raise ValueError(
                f"Project.status must be a valid ProjectStatus value. "
                f"Got '{project.status}', expected one of: {valid_values}"
            )


class Page(Base):
    """A page in a proofreading project.

    This corresponds to a specific page in a PDF.
    """

    __tablename__ = "proof_pages"

    #: Primary key.
    id = pk()
    #: The project that owns this page.
    project_id = foreign_key("proof_projects.id")
    #: Human-readable ID, which we display in the URL.
    slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    #: UUID (for s3 uploads, stability despite slug renames, etc.)
    uuid = Column(String, unique=True, nullable=False, default=_create_uuid)
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
        order_by=lambda: Revision.created_at,
        backref="page",
        cascade="delete",
    )

    def __str__(self) -> str:
        return self.slug

    def s3_path(self, bucket: str) -> S3Path:
        return S3Path(bucket=bucket, key=f"assets/pages/{self.uuid}.jpg")

    def cloudfront_url(self, base_url: str) -> str:
        return f"{base_url}/pages/{self.uuid}.jpg"


class PageStatus(Base):
    """The transcription status of a given page.

    For specific values, see `ambuda.seed.lookup.page_status`.
    """

    __tablename__ = "proof_page_statuses"

    #: Primary key.
    id = pk()
    #: A short human-readable label for this status.
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    def __str__(self) -> str:
        return self.name


class RevisionBatch(Base):
    """A batch of revisions created together.

    Used to track and dedupe related revisions.
    """

    __tablename__ = "proof_revision_batches"

    #: Primary key.
    id = pk()
    #: The user who created this batch.
    user_id = foreign_key("users.id")
    #: Timestamp at which this batch was created.
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )

    #: The user who created this batch.
    user = relationship("User", backref="revision_batches")


class Revision(Base):
    """A specific page revision.

    To get the latest revision, sort by `created_at`.
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
    #: The batch this revision belongs to (for bulk operations).
    batch_id = Column(
        Integer, ForeignKey("proof_revision_batches.id"), index=True, nullable=True
    )
    #: Page status
    status_id = Column(
        Integer, ForeignKey("proof_page_statuses.id"), index=True, nullable=False
    )
    #: Timestamp at which this revision was created.
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
    #: An optional editor summary for this revision.
    summary = Column(Text_, nullable=False, default="")
    #: The actual content of this revision.
    content: Mapped[str] = mapped_column(Text_, nullable=False)

    #: An ordered list of revisions for this page (newest first).
    author = relationship("User", backref="revisions")
    #: The project this revision belongs to.
    project = relationship("Project")
    #: The status of this page.
    status = relationship("PageStatus", backref="revisions")
    #: The batch this revision belongs to.
    batch = relationship("RevisionBatch", backref="revisions")

    @property
    def created(self):
        return self.created_at


class SuggestionStatus(StrEnum):
    """The status of a suggestion."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Suggestion(Base):
    """A suggested edit from a non-P1 or anonymous user.

    (P1 reviewers can accept or reject suggestions.)
    """

    __tablename__ = "proof_suggestions"

    #: Primary key.
    id = pk()
    #: The project this suggestion is for.
    project_id = foreign_key("proof_projects.id")
    #: The page this suggestion is for.
    page_id = foreign_key("proof_pages.id")
    #: The revision against which this suggestion was made.
    revision_id = foreign_key("proof_revisions.id")
    #: The user who made the suggestion (null for anonymous).
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=True)
    #: Group batches of suggestions.
    batch_id: Mapped[str] = mapped_column(String, nullable=False, default=_create_uuid)
    #: Timestamp at which this suggestion was created.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )
    #: The suggested page content.
    content: Mapped[str] = mapped_column(Text_, nullable=False)
    #: An explanation from the suggester.
    explanation: Mapped[str] = mapped_column(String, nullable=False, default="")
    #: The status of this suggestion.
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=SuggestionStatus.PENDING
    )

    project = relationship("Project")
    page = relationship("Page")
    revision = relationship("Revision")
    user = relationship("User")


@event.listens_for(Suggestion, "before_insert")
@event.listens_for(Suggestion, "before_update")
def validate_suggestion_status(mapper, connection, suggestion):
    if suggestion.status:
        try:
            SuggestionStatus(suggestion.status)
        except ValueError:
            valid_values = ", ".join([s.value for s in SuggestionStatus])
            raise ValueError(
                f"Suggestion.status must be a valid SuggestionStatus value. "
                f"Got '{suggestion.status}', expected one of: {valid_values}"
            )


@event.listens_for(Suggestion, "before_insert")
@event.listens_for(Suggestion, "before_update")
def validate_suggestion_lengths(mapper, connection, suggestion):
    if suggestion.content and len(suggestion.content) > 50_000:
        raise ValueError("Suggestion.content must be at most 50,000 characters.")
    if suggestion.explanation and len(suggestion.explanation) > 1_000:
        raise ValueError("Suggestion.explanation must be at most 1,000 characters.")
