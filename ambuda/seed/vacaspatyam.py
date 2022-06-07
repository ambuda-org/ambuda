#!/usr/bin/env python3
"""Add the Vacaspatyam to the database."""

from ambuda.seed.cdsl_utils import create_from_scratch
from ambuda.seed.common import (
    fetch_bytes,
    create_db,
    unzip_and_read,
)

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/VCPScan/2020/downloads/vcpxml.zip"
)


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/vcp.xml")

    print("Adding items to database ...")
    create_from_scratch(engine, slug="v", title="Vacaspatyam", xml_blob=xml_blob)

    print("Done.")


if __name__ == "__main__":
    run()
