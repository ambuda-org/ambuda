from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from ambuda.models.base import db, foreign_key, pk


class Dictionary(db.Model):

    """A dictionary that maps Sanskrit expressions to definitions in
    various languages."""

    __tablename__ = "dictionaries"

    #: Primary key.
    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, unique=True, nullable=False)
    #: Human-readable dictionary title.
    title = Column(String, nullable=False)

    entries = relationship("DictionaryEntry", backref="dictionary", cascade="delete")


class DictionaryEntry(db.Model):

    """Dictionary definitions for a specific entry key.

    A given key is allowed to have multiple entries.
    """

    __tablename__ = "dictionary_entries"

    #: Primary key.
    id = pk()
    #: The dictionary this entry belongs to.
    dictionary_id = foreign_key("dictionaries.id")
    #: A standardized lookup key for this entry.
    #: For the standardization logic, see `dict_utils.standardize_key`.
    key = Column(String, index=True, nullable=False)
    #: XML payload. We convert this to HTML at serving time.
    value = Column(String, nullable=False)
