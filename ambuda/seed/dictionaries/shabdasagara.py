#!/usr/bin/env python3
"""Add the Shabda-sagara dictionary to the database."""

from ambuda.seed.utils.cdsl_utils import create_from_scratch, iter_entries_as_strings
from ambuda.seed.utils.itihasa_utils import create_db, fetch_bytes, unzip_and_read
from ambuda.utils.dict_utils import standardize_key

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/SHSScan/2020/downloads/shsxml.zip"
)


def shs_generator(xml_blob: str):
    for key, value in iter_entries_as_strings(xml_blob):
        key = standardize_key(key)
        yield key, value


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Fetching data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/shs.xml")

    print("Adding items to database ...")
    create_from_scratch(
        engine,
        slug="shabdasagara",
        title="Shabda-Sagara (1900)",
        generator=shs_generator(xml_blob),
    )

    print("Done.")


if __name__ == "__main__":
    run()
