"""Models for parsed Sanskrit text data."""

from sqlalchemy import Column
from sqlalchemy import Text as _Text

from ambuda.models.base import db, foreign_key, pk


class BlockParse(db.Model):
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
    #: searchable. For now, it is just a 3-column TSV string.
    data = Column(_Text, nullable=False)
