"""Models for parse data."""

from sqlalchemy import (
    Column,
    Text as _Text,
)

from ambuda.models.base import Base, pk, foreign_key


class BlockParse(Base):
    """Parse data for a `TextBlock`."""

    __tablename__ = "block_parses"

    #: Primary key.
    id = pk()
    #: The text this data corresponds to.
    text_id = foreign_key("texts.id")
    #: The block this data corresponds to.
    block_id = foreign_key("text_blocks.id")
    #: The parse data as a semi-structured text blob.
    #: As Ambuda matures, we can make this field more structured and
    #: searchable.
    data = Column(_Text, nullable=False)
