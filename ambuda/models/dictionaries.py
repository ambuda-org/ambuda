from sqlalchemy import (
    Column,
    String,
)
from sqlalchemy.orm import relationship

from ambuda.models.base import Base, pk, foreign_key


class Dictionary(Base):
    __tablename__ = "dictionaries"

    id = pk()
    #: Human-readable ID, which we display in the URL.
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)

    entries = relationship("DictionaryEntry", backref="dictionary", cascade="delete")


class DictionaryEntry(Base):
    __tablename__ = "dictionary_entries"

    id = pk()
    dictionary_id = foreign_key("dictionaries.id")
    #: A standardized lookup key for this entry.
    #: We standardize by e.g. applying parasavarṇa rules. For more examples, see
    #: `dict_utils.standardize_key`.
    key = Column(String, index=True, nullable=False)
    #: XML payload. We convert this to HTML at serving time.
    value = Column(String, nullable=False)
