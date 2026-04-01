"""Models for text documents in our library.

We define texts with three different tables:

- `Text` defines the text as a whole.
- `TextSection` defines ordered sections of a `Text`.
- `TextBlock` is typically a verse or paragraph within a `TextSection`.
"""

import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    JSON,
    Table,
    event,
)
from sqlalchemy import Text as _Text
from sqlalchemy import select, exists
from sqlalchemy.orm import (
    backref,
    relationship,
    Mapped,
    mapped_column,
    object_session,
    validates,
)

from ambuda.models.base import Base, foreign_key, pk
from ambuda.utils.s3 import S3Path


class TitleConfig(BaseModel):
    fixed: dict[str, str] = Field(default_factory=dict)
    patterns: dict[str, str] = Field(default_factory=dict)


class TextConfig(BaseModel):
    titles: TitleConfig = Field(default_factory=TitleConfig)


class TextStatus(StrEnum):
    P0 = "p0"
    P1 = "p1"
    P2 = "p2"


text_collection_association = Table(
    "text_collection_association",
    Base.metadata,
    Column(
        "text_id", Integer, ForeignKey("texts.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "collection_id",
        Integer,
        ForeignKey("text_collections.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class TextCollection(Base):
    """A collection for organizing texts hierarchically."""

    __tablename__ = "text_collections"

    #: Primary key.
    id = pk()
    #: The parent collection (nullable for top-level collections).
    parent_id = foreign_key("text_collections.id", nullable=True)
    #: URL-friendly name.
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    #: Ordering within the parent collection.
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Human-readable title.
    title: Mapped[str] = mapped_column(String, nullable=False)
    #: Optional description (Markdown).
    description: Mapped[str | None] = mapped_column(_Text, nullable=True)
    #: When this collection was created.
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    parent = relationship("TextCollection", remote_side=[id], backref="children")
    texts = relationship(
        "Text",
        secondary=text_collection_association,
        back_populates="collections",
    )

    def __str__(self):
        return self.title


class Text(Base):
    """A text with its metadata."""

    __tablename__ = "texts"

    #: Primary key.
    id = pk()
    #: Human-readable ID, which we display in the URL.
    #: Must not contain "." since dots delimit block slugs in URLs.
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    #: Slugs that conflict with sub-routes under /texts/.
    RESERVED_SLUGS = frozenset({"catalog", "downloads"})

    @validates("slug")
    def validate_slug(self, _key, value):
        if "." in value:
            raise ValueError(f"Text slug must not contain '.': {value!r}")
        if value in self.RESERVED_SLUGS:
            raise ValueError(f"Text slug is reserved: {value!r}")
        return value

    #: The title of this text.
    title: Mapped[str] = mapped_column(String, nullable=False)
    #: Metadata for this text, as a <teiHeader> element.
    #: This is public-facing metadata as part of a TEI document.
    header: Mapped[str | None] = mapped_column(_Text)
    #: Additional metadata for this text as a JSON document.
    #: This is mainly for ambuda-internal notes on heading names, etc.
    # NOTE: `meta` is reserved by WTForms and `metadata` has other meanings in sqlalchemy,
    # NOTE: so just call this `config`.
    #: The schema is defined in `TextConfig`.
    config = Column(JSON, nullable=True)
    language: Mapped[str] = mapped_column(String, nullable=False, default="sa")
    status: Mapped[str | None] = mapped_column(String, nullable=True)

    #: Timestamp at which this text was created.
    #: Nullable for legacy reasons.
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=True)
    #: Timestamp at which this text was published.
    published_at = Column(DateTime, nullable=True)
    #: Timestamp at which this text was updated.
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)

    genre_id = foreign_key("genres.id", nullable=True)
    #: The project that created this text.
    project_id = foreign_key("proof_projects.id", nullable=True)
    # The text's author.
    author_id = foreign_key("authors.id", nullable=True)
    # The parent text that this text corresponds to.
    # (Non-null for translations, commentaries, etc.)
    parent_id = foreign_key("texts.id", nullable=True)

    #: An ordered list of the sections contained within this text.
    sections = relationship(
        "TextSection",
        backref="text",
        cascade="delete",
        order_by="TextSection.order",
    )
    #: The genre this text belongs to.
    genre = relationship("Genre", backref="texts")
    #: The project that created this text.
    project = relationship("Project", backref="texts")
    #: The author that created this text.
    author = relationship("Author", backref="texts")
    # The parent text that this text corresponds to.
    parent = relationship("Text", remote_side=[id], backref="children")
    # The exports associated with this text.
    exports = relationship("TextExport", backref="text", cascade="delete")
    collections = relationship(
        "TextCollection",
        secondary=text_collection_association,
        back_populates="texts",
    )

    #: Alternative titles for this text (used for search).
    alternate_titles = relationship(
        "TextAlternateTitle", backref="text", cascade="all, delete-orphan"
    )

    # DEPRECATED parse data
    block_parses = relationship("BlockParse", backref="text")

    def __repr__(self) -> str:
        return f"Text(slug={self.slug})"

    def __str__(self) -> str:
        return self.slug

    @property
    def supports_text_export(self) -> bool:
        """Temporary prop while we support Celery-based export."""
        return len(self.sections) < 20

    @property
    def is_p0(self) -> bool:
        """Return whether the text is unproofed."""
        return self.status == TextStatus.P0

    @property
    def has_parse_data(self) -> bool:
        from ambuda.models.parse import BlockParse, TokenBlock

        session = object_session(self)
        if not session:
            return False

        return (
            session.scalar(
                select(
                    exists().where(BlockParse.text_id == self.id)
                    | exists().where(TokenBlock.text_id == self.id)
                )
            )
            or False
        )


@event.listens_for(Text, "before_insert")
@event.listens_for(Text, "before_update")
def validate_text(mapper, connection, text):
    if text.config:
        try:
            json.loads(text.config)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Text.config must be a valid JSON document: {e}")
    if text.status:
        try:
            TextStatus(text.status)
        except ValueError:
            valid_values = ", ".join([s.value for s in TextStatus])
            raise ValueError(
                f"Text.status must be a valid TextStatus value. "
                f"Got '{text.status}', expected one of: {valid_values}"
            )


class TextSection(Base):
    """Ordered divisions of text content. This represent divisions like kāṇḍas,
    sargas, etc.

    A TextSection is the "unit of viewing." By default, Ambuda will display a
    text one section at a time.

    NOTE: sections are not nested.
    """

    __tablename__ = "text_sections"

    #: Primary key.
    id = pk()
    #: The text that contains this section.
    text_id = foreign_key("texts.id")
    #: Human-readable ID, which we display in the URL.
    #:
    #: Slugs are hierarchical, with different levels of the hierarchy separated
    #: by "." characters. At serving time, we rely on this property to properly
    #: organize a text into different sections.
    slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    #: The title of this section.
    #: TODO: is this still necessary? consider dropping.
    title: Mapped[str] = mapped_column(String, nullable=False)
    #: Explicit ordering within the parent text.
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: An ordered list of the blocks contained within this section.
    blocks = relationship(
        "TextBlock", backref="section", order_by=lambda: TextBlock.n, cascade="delete"
    )

    def __str__(self) -> str:
        return self.slug


text_block_associations = Table(
    "text_block_associations",
    Base.metadata,
    Column("parent_id", Integer, ForeignKey("text_blocks.id"), primary_key=True),
    Column("child_id", Integer, ForeignKey("text_blocks.id"), primary_key=True),
)


class TextBlock(Base):
    """A verse or paragraph.

    A TextBlock is the "unit of reuse." When we make cross-references between
    texts, we do so at the TextBlock level.
    """

    __tablename__ = "text_blocks"

    #: Primary key.
    id = pk()
    #: The text this block belongs to.
    text_id = foreign_key("texts.id")
    #: The section this block belongs to.
    section_id = foreign_key("text_sections.id")
    #: The proofing page this block came from.
    page_id = foreign_key("proof_pages.id", nullable=True)
    #: Human-readable ID, which we display in the URL.
    slug: Mapped[str] = mapped_column(String, index=True, nullable=False)
    #: Raw XML content, which we translate into HTML at serving time.
    xml = Column(_Text, nullable=False)
    #: (internal-only) Block A comes before block B iff A.n < B.n.
    n = Column(Integer, nullable=False)

    text = relationship("Text")
    page = relationship("Page", backref="text_blocks")

    children = relationship(
        "TextBlock",
        secondary=text_block_associations,
        primaryjoin="TextBlock.id==text_block_associations.c.parent_id",
        secondaryjoin="TextBlock.id==text_block_associations.c.child_id",
        order_by="TextBlock.n",
        backref="parents_backref",
    )

    # Parents: blocks that are parents of this block (e.g., verses that this commentary references)
    parents = relationship(
        "TextBlock",
        secondary=text_block_associations,
        primaryjoin="TextBlock.id==text_block_associations.c.child_id",
        secondaryjoin="TextBlock.id==text_block_associations.c.parent_id",
        order_by="TextBlock.n",
        viewonly=True,
    )

    def __str__(self) -> str:
        return self.slug


class Author(Base):
    """The author of some text."""

    __tablename__ = "authors"

    #: Primary key.
    id = pk()
    #: The author's name.
    name = Column(String, nullable=False)
    #: The author's URL identifier.
    slug = Column(String, unique=True, nullable=False)
    #: A markdown description of the author.
    description = Column(_Text, nullable=True)

    def __str__(self):
        # Include slug because author names are not unique.
        return f"{self.name} ({self.slug})"


class TextExport(Base):
    """A catalog of text exports."""

    __tablename__ = "text_exports"

    id = pk()
    #: The text this export belongs to.
    text_id = foreign_key("texts.id")
    #: A unique identifier for this export.
    slug: Mapped[str] = mapped_column(String, unique=True)
    #: The type of export (plain_text, xml, pdf, tokens).
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    #: The path to this resource on S3.
    s3_path: Mapped[str] = mapped_column(String)
    #: Size in bytes
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    #: SHA256 checksum of the file contents
    sha256_checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    #: When this export was last updated.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    @property
    def export_config(self) -> "ExportConfig | None":
        from ambuda.utils.text_exports import EXPORTS

        try:
            return next(x for x in EXPORTS if x.matches(self.slug))
        except StopIteration:
            return None

    def asset_url(self, base_url: str) -> str | None:
        """Return the CloudFront URL for this export, or None if not an asset."""
        return S3Path.from_path(self.s3_path).to_asset_url(base_url)


class BulkExport(Base):
    """A catalog of bulk exports (e.g. ZIP archives of all texts)."""

    __tablename__ = "bulk_exports"

    id = pk()
    #: A unique identifier for this export (e.g. "ambuda-xml.zip").
    slug: Mapped[str] = mapped_column(String, unique=True)
    #: The type of bulk export.
    export_type: Mapped[str] = mapped_column(String, nullable=False)
    #: The path to this resource on S3.
    s3_path: Mapped[str] = mapped_column(String, nullable=False)
    #: Size in bytes.
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    #: SHA256 checksum of the file contents.
    sha256_checksum: Mapped[str | None] = mapped_column(String, nullable=True)
    #: When this export was last updated.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )

    def asset_url(self, base_url: str) -> str | None:
        """Return the CloudFront URL for this export, or None if not an asset."""
        return S3Path.from_path(self.s3_path).to_asset_url(base_url)


class TextReport(Base):
    """A stored validation report for a text."""

    __tablename__ = "text_reports"

    id = pk()
    #: The text this report belongs to.
    text_id = foreign_key("texts.id")
    #: When this report was created.
    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    #: When this report was last updated.
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    #: The validation report payload as JSON.
    payload = Column(JSON, nullable=False)
    #: Lightweight summary: {"num_passed": int, "num_total": int}
    summary = Column(JSON, nullable=True)

    text = relationship(
        "Text",
        backref=backref("reports", cascade="all, delete-orphan"),
    )

    @staticmethod
    def rerun_lock_key(text_id: int) -> str:
        return f"report_rerun:{text_id}"


class TextAlternateTitle(Base):
    """An alternative title for a text, used for search."""

    __tablename__ = "text_alternate_titles"

    #: Primary key.
    id = pk()
    #: The text this alternate title belongs to.
    text_id = foreign_key("texts.id")
    #: The alternative title.
    title: Mapped[str] = mapped_column(String, nullable=False, index=True)

    def __str__(self):
        return self.title


class TextBlockBookmark(Base):
    """Bookmarks on a text."""

    __tablename__ = "text_block_bookmarks"

    #: The user that created this bookmark.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    #: The block that the user has bookmarked.
    block_id: Mapped[int] = mapped_column(
        ForeignKey("text_blocks.id"), primary_key=True
    )
    #: When the bookmark was created.
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    #: Relationships
    block = relationship("TextBlock", backref="bookmarks")
    user = relationship("User", backref="bookmarks")
