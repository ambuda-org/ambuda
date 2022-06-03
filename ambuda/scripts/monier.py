#!/usr/bin/env python3
"""Add the Monier-Williams dictionary to the database."""

import io
import pathlib
import sys
import zipfile

from sqlalchemy import create_engine
from xml.etree import ElementTree as ET

from ambuda.database import DATABASE_URI, entries, metadata
from ambuda.scripts.common import fetch_bytes


ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/MWScan/2020/downloads/mwxml.zip"
)


def fetch_mw_xml() -> str:
    zip_bytes = fetch_bytes(ZIP_URL)
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as ref:
        with ref.open("xml/mw.xml") as f:
            return f.read()


def iter_xml(blob: str):
    root = ET.fromstring(blob)

    for child in root:
        tag_str = (
            "H1 H1A H1B H1C H1E H2 H2A H2B H2C H2E "
            "H3 H3A H3B H3C H3E H4 H4A H4B H4C H4E"
        )
        allowed_tags = set(tag_str.split())
        assert child.tag in allowed_tags, child.tag

        # NOTE: `key` is not unique.
        key = None
        for elem in child.iter():
            if elem.tag == "key1":
                key = elem.text
                break
        value = ET.tostring(child, encoding="utf-8")

        assert key and value
        yield key, value


def create_db():
    engine = create_engine(DATABASE_URI)
    metadata.create_all(engine)
    return engine


def insert(engine, mw_xml: str):
    ins = entries.insert()
    print("Adding items to database ...")
    with engine.connect() as conn:
        items = [{"key": key, "value": value} for key, value in iter_xml(mw_xml)]
        conn.execute(ins, items)
    print("Done.")


def run():
    engine = create_db()
    mw_xml = fetch_mw_xml()
    insert(engine, mw_xml)


if __name__ == "__main__":
    run()
