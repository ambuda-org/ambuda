#!/usr/bin/env python3
"""Add the Vacaspatyam to the database."""

from ambuda.seed.cdsl_utils import create_from_scratch
from ambuda.seed.common import (
    fetch_bytes,
    create_db,
    unzip_and_read,
)

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/SKDScan/2013/downloads/skdxml.zip"
)


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/skd.xml")

    print("Adding items to database ...")
    create_from_scratch(
        engine, slug="skd", title="Śabdakalpadrumaḥ (1886)", xml_blob=xml_blob
    )

    print("Done.")


if __name__ == "__main__":
    run()
