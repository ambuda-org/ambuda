#!/usr/bin/env python3
"""Add the Vacaspatyam to the database."""
from ambuda.dict_utils import standardize_key
from ambuda.seed.cdsl_utils import create_from_scratch, iter_xml
from ambuda.seed.common import (
    fetch_bytes,
    create_db,
    unzip_and_read,
)

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/VCPScan/2020/downloads/vcpxml.zip"
)


def v_generator(xml_blob: str):
    for key, value in iter_xml(xml_blob):
        key = standardize_key(key)
        yield key, value


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/vcp.xml")

    print("Adding items to database ...")
    create_from_scratch(
        engine, slug="v", title="Vācaspatyam (1873)", generator=v_generator(xml_blob)
    )

    print("Done.")


if __name__ == "__main__":
    run()
