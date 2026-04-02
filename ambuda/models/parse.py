"""Models for parsed Sanskrit text data."""

from datetime import datetime, UTC

from sqlalchemy import Column
from sqlalchemy import DateTime, Integer, String, Text as _Text
from sqlalchemy.orm import relationship, Mapped, mapped_column

from ambuda.models.base import Base, foreign_key, pk
from ambuda.enums import TokenBlockStatus


class Token(Base):
    """A single word in a parsed block."""

    __tablename__ = "tokens"

    #: Primary key.
    id = pk()
    #: The surface form of this token.
    form = Column(String, nullable=False)
    #: The base for of this token.
    base = Column(String, nullable=False)
    #: The parse data for this token.
    parse = Column(String, nullable=False)
    #: The block this token belongs to.
    block_id = foreign_key("text_blocks.id")
    #: The order of this token within the block.
    order = Column(Integer, nullable=False)

    block = relationship("TextBlock", backref="tokens")


class TokenBlock(Base):
    """Represents all of the tokens associated with some TextBlock.

    We use TokenBlock to store a `version` for optimistic concurrency control when
    creating a new `TextRevision`.
    """

    __tablename__ = "token_blocks"

    #: Primary key.
    id = pk()
    #: The text this token block corresponds to.
    text_id = foreign_key("texts.id", ondelete="CASCADE")
    #: The block this data corresponds to.
    block_id = foreign_key("text_blocks.id", ondelete="CASCADE")
    #: (internal-only) used only so that we can implement optimistic locking
    #: for edit conflicts. See the `add_revision` function for details.
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=TokenBlockStatus.R0
    )

    text = relationship("Text", backref="token_blocks")
    block = relationship("TextBlock", backref="token_blocks")


class TokenRevision(Base):
    """A revision to a block's tokens.

    The usage of TokenRevision is similar to the usage of `db.Revision` for ordinary
    proofing projects.
    """

    __tablename__ = "token_revisions"

    #: Primary key.
    id = pk()
    #: The parse data as a semi-structured text blob.
    #: As Ambuda matures, we can make this field more structured and
    #: searchable. For now, it is just a 3-column TSV string.
    data = Column(_Text, nullable=False)
    #: The status of this revision.
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=TokenBlockStatus.R0
    )
    #: The token block this data corresponds to.
    token_block_id = foreign_key("token_blocks.id")
    #: The author of this revision.
    author_id = foreign_key("users.id")
    #: Timestamp at which this revision was created.
    created_at = Column(
        DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False
    )

    author = relationship("User", backref="token_revisions")
    block = relationship("TokenBlock", backref="revisions")


class BlockParse(Base):
    """Parse data for a `TextBlock`.

    DEPRECATED -- use Token, TokenBlock, and TokenRevision instead.
    """

    __tablename__ = "block_parses"

    #: Primary key.
    id = pk()
    #: The text this data corresponds to.
    text_id = foreign_key("texts.id", ondelete="CASCADE")
    #: The block this data corresponds to.
    block_id = foreign_key("text_blocks.id", ondelete="CASCADE")
    #: The parse data as a semi-structured text blob.
    #: As Ambuda matures, we can make this field more structured and
    #: searchable. For now, it is just a 3-column TSV string.
    data = Column(_Text, nullable=False)
