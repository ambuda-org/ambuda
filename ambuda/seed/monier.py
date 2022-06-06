#!/usr/bin/env python3
"""Add the Monier-Williams dictionary to the database."""

import itertools
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
    tag_str = (
        "H1 H1A H1B H1C H1E H2 H2A H2B H2C H2E " "H3 H3A H3B H3C H3E H4 H4A H4B H4C H4E"
    )
    allowed_tags = set(tag_str.split())

    for _, elem in ET.iterparse(io.BytesIO(blob), events=["end"]):
        if elem.tag not in allowed_tags:
            continue

        # NOTE: `key` is not unique.
        key = None
        for child in elem.iter():
            if child.tag == "key1":
                key = child.text
                break
        value = ET.tostring(elem, encoding="utf-8")

        assert key and value
        assert len(value) > 50, value
        yield key, value
        elem.clear()


def batches(generator, n):
    while True:
        batch = list(itertools.islice(generator, n))
        if batch:
            yield batch
        else:
            return

        if elem.tag in allowed_tags:
            elem.clear()


def batches(generator, n):
    while True:
        batch = list(itertools.islice(generator, n))
        if batch:
            yield batch
        else:
            return


def batches(generator, n):
    while True:
        batch = list(itertools.islice(generator, n))
        if batch:
            yield batch
        else:
            return


def insert(engine, mw_xml: str):
    delete_existing_dict(engine, "mw")

    with Session(engine) as session:
        dictionary = db.Dictionary(
            slug="mw", title="Monier-Williams Sanskrit-English Dictionary (1899)"
        )
        session.add(dictionary)
        session.commit()

        dictionary_id = dictionary.id

    assert dictionary_id

    entries = db.DictionaryEntry.__table__
    ins = entries.insert()
    with engine.connect() as conn:
        for i, batch in enumerate(batches(iter_xml(mw_xml), 10000)):
            items = [
                {"dictionary_id": dictionary_id, "key": key, "value": value}
                for key, value in batch
            ]
            conn.execute(ins, items)
            print(10000 * (i + 1))


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
