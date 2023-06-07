"""Models for text documents in our library.

We define texts with three different tables:

- `Text` defines the text as a whole.
- `TextSection` defines ordered sections of a `Text`.
- `TextBlock` is typically a verse or paragraph within a `TextSection`.
"""

from ambuda.models.base import Base, foreign_key, pk
from sqlalchemy import Column, Integer, String
from sqlalchemy import Text as _Text
from sqlalchemy.orm import relationship


class Text(Base):

    """A text with its metadata."""

    __tablename__ = "texts"

    #: Primary key.
    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, unique=True, nullable=False)
    #: The title of this text.
    title = Column(String, nullable=False)
    #: Metadata for this text, as a <teiHeader> element.
    header = Column(_Text)
    #: An ordered list of the sections contained within this text.
    sections = relationship("TextSection", backref="text", cascade="delete")
    #: Add a genre for the text
    genre_id = foreign_key("genres.id")
    genre = relationship("Genre")

    def __str__(self):
        return self.slug


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
    slug = Column(String, index=True, nullable=False)
    #: The title of this section.
    title = Column(String, nullable=False)
    #: An ordered list of the blocks contained within this section.
    blocks = relationship(
        "TextBlock", backref="section", order_by=lambda: TextBlock.n, cascade="delete"
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
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, index=True, nullable=False)
    #: Raw XML content, which we translate into HTML at serving time.
    xml = Column(_Text, nullable=False)
    #: (internal-only) Block A comes before block B iff A.n < B.n.
    n = Column(Integer, nullable=False)

    text = relationship("Text")
