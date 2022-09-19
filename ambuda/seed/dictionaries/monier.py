#!/usr/bin/env python3
"""Add the Monier-Williams dictionary to the database."""

from ambuda.seed.utils.cdsl_utils import create_from_scratch, iter_entries_as_strings
from ambuda.seed.utils.data_utils import create_db, fetch_bytes, unzip_and_read
from ambuda.utils.dict_utils import standardize_key

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/MWScan/2020/downloads/mwxml.zip"
)


def mw_generator(xml_blob: str):
    for key, value in iter_entries_as_strings(xml_blob):
        key = standardize_key(key)
        yield key, value


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/mw.xml")

    print("Adding items to database ...")
    create_from_scratch(
        engine,
        slug="mw",
        title="Monier-Williams Sanskrit-English Dictionary (1899)",
        generator=mw_generator(xml_blob),
    )

    print("Done.")


if __name__ == "__main__":
    run()
