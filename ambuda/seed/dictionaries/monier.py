#!/usr/bin/env python3
"""Add the Monier-Williams dictionary to the database."""

from ambuda.seed.utils.cdsl_utils import create_from_scratch, iter_entries_as_strings
from ambuda.seed.utils.data_utils import fetch_bytes, unzip_and_read
from ambuda.utils.dict_utils import standardize_key

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/MWScan/2020/downloads/mwxml.zip"
)


def mw_generator(xml_blob: str):
    for key, value in iter_entries_as_strings(xml_blob):
        key = standardize_key(key)
        yield key, value


def run(session, spec, use_cache=False):
    title = spec.title

    print(f"Fetching {title} data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/mw.xml")

    print(f"Adding {title} items to database ...")
    create_from_scratch(
        session,
        slug=spec.slug,
        title=title,
        generator=mw_generator(xml_blob),
    )

    print("Done.")
