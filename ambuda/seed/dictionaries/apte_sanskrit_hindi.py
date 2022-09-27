#!/usr/bin/env python3
"""Add Apte's Sanskrit-Hindi dictionary to the database.

Professor Amba Kulkarni's group at the University of Hyderabad has published a
digitized version of Apte's Sanskrit-Hindi dictionary, which is available from
their main GitHub repo (https://github.com/samsaadhanii/scl). But since the
repo as a whole ,is quite large (>250 MiB even with `--depth 1`), we download
just the data we want via simple HTTP requests.

The dictionary is sharded into several XML files by first letter. A sample file:

    https://github.com/samsaadhanii/scl/blob/master/MT/data/hi/Apte_dict/au.xml

And a sample entry:

    <lexhead no="2">
    <dentry>औक्थिक्यम्</dentry>
    <prAwipaxikam>औक्थिक्य</prAwipaxikam>
    <grammar>नपुं*</grammar>
    <etymology>[उक्थ+ठक्+ष्यञ्]</etymology>
    <sense no="1">उक्थ का पाठ</sense>
    </lexhead>

"""

import io
import re
import xml.etree.ElementTree as ET
from typing import Iterator

import click
from indic_transliteration import sanscript

from ambuda.seed.utils.cdsl_utils import create_from_scratch
from ambuda.seed.utils.data_utils import create_db, fetch_text
from ambuda.utils.dict_utils import standardize_key


#: All of the first letters used in the dictionary data.
LETTERS = [
    "a",
    "aa",
    "i",
    "ii",
    "u",
    "uu",
    "q",
    # "r̥̄" is in `q.xml`. Not sure where "ḷ" is.
    "e",
    "ai",
    "o",
    "au",
    "k",
    "kh",
    "g",
    "gh",
    # Not sure where "ṅ" is.
    "c",
    "ch",
    "j",
    "jh",
    # Not sure where "ñ" is.
    "t",
    "th",
    "d",
    "dh",
    "nn",
    "w",
    "wh",
    "x",
    "xh",
    "n",
    "p",
    "ph",
    "b",
    "bh",
    "y",
    "r",
    "l",
    "v",
    "sh",
    "ss",
    "s",
    "h",
]


#: URL template for Apte data
RAW_URL = (
    "https://github.com/samsaadhanii/scl/raw/master/MT/data/hi/Apte_dict/{letter}.xml"
)


def _get_text(xml, path: str) -> str:
    try:
        return xml.find(path).text
    except AttributeError:
        return ""


def _iter_entries_as_xml(blobs: list[str]) -> Iterator[tuple[str, str]]:
    for blob in blobs:
        xml = ET.fromstring(blob)
        for entry in xml:
            assert entry.tag == "lexhead"

            key = _get_text(entry, "./dentry")
            key = sanscript.transliterate(key, sanscript.DEVANAGARI, sanscript.SLP1)
            value = ET.tostring(entry, encoding="utf-8").decode("utf-8")
            yield key, value


@click.command()
@click.option("--use-cache/--no-use-cache", default=False)
def run(use_cache):
    print("Initializing database ...")
    engine = create_db()

    print(f"Fetching data from GitHub (use_cache = {use_cache})...")

    blobs = []
    for letter in LETTERS:
        url = RAW_URL.format(letter=letter)
        print(f"- Fetching {letter} ({url})")
        blob = fetch_text(url, read_from_cache=use_cache)
        blobs.append(blob)

    create_from_scratch(
        engine,
        slug="apte-sh",
        title="संस्कृत-हिन्दी कोश (आप्टे, 1966)",
        generator=_iter_entries_as_xml(blobs),
    )


if __name__ == "__main__":
    run()
