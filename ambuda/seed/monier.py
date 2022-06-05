#!/usr/bin/env python3
"""Add the Monier-Williams dictionary to the database."""

import io
import zipfile
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.seed.common import fetch_bytes, create_db, delete_existing_dict

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


def insert(engine, mw_xml: str):
    delete_existing_dict(engine, "mw")
    with Session(engine) as session:
        dictionary = db.Dictionary(
            slug="mw", title="Monier-Williams Sanskrit-English Dictionary (1899)"
        )
        session.add(dictionary)
        session.commit()

        dictionary_id = dictionary.id

    items = [
        {"dictionary_id": dictionary_id, "key": key, "value": value}
        for key, value in iter_xml(mw_xml)
    ]
    entries = db.DictionaryEntry.__table__
    ins = entries.insert()
    with engine.connect() as conn:
        for r in range(0, len(items), 10000):
            batch = items[r : r + 10000]
            conn.execute(ins, batch)
            print(r)


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    mw_xml = fetch_mw_xml()

    print("Adding items to database ...")
    insert(engine, mw_xml)

    print("Done.")


if __name__ == "__main__":
    run()
