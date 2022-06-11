#!/usr/bin/env python3
"""Add the Vacaspatyam to the database."""
from ambuda.dict_utils import standardize_key
from ambuda.seed.cdsl_utils import create_from_scratch, iter_entries_as_strings
from ambuda.seed.common import (
    fetch_bytes,
    create_db,
    unzip_and_read,
)

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/SKDScan/2013/downloads/skdxml.zip"
)


def s_generator(xml_blob: str):
    for key, value in iter_entries_as_strings(xml_blob):
        key = standardize_key(key)
        yield key, value


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/skd.xml")

    print("Adding items to database ...")
    create_from_scratch(
        engine,
        slug="skd",
        title="Śabdakalpadrumaḥ (1886)",
        generator=s_generator(xml_blob),
    )

    print("Done.")


if __name__ == "__main__":
    run()
