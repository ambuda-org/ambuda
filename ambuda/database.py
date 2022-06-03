import pathlib
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData
from xml.etree import ElementTree as ET


DATABASE_URI = "sqlite:///monier.db"

metadata = MetaData()

entries = Table(
    "dict_entries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("key", String, index=True, nullable=False),
    Column("value", String, nullable=False),
)
