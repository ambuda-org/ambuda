import pathlib

from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text as _Text,
    ForeignKey,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
)


DATABASE_URI = "sqlite:///database.db"


Base = declarative_base()


def pk():
    return Column(Integer, primary_key=True)


def foreign_key(field):
    return Column(Integer, ForeignKey(field), nullable=False, index=True)


class Text(Base):
    __tablename__ = "texts"

    id = pk()
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)

    sections = relationship("TextSection", backref="text", cascade="delete")


class TextSection(Base):
    __tablename__ = "text_sections"

    id = pk()
    text_id = foreign_key("texts.id")
    slug = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    # TODO: move to TextUnit?
    xml = Column(_Text, nullable=False)


class Dictionary(Base):
    __tablename__ = "dictionaries"

    id = pk()
    slug = Column(String, unique=True, nullable=False)
    title = Column(String, nullable=False)

    entries = relationship("DictionaryEntry", backref="dictionary", cascade="delete")


class DictionaryEntry(Base):
    __tablename__ = "dictionary_entries"

    id = pk()
    dictionary_id = foreign_key("dictionaries.id")
    key = Column(String, index=True, nullable=False)
    value = Column(String, nullable=False)
