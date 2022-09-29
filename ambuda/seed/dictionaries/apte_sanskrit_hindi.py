#!/usr/bin/env python3
"""Add Apte's Sanskrit-Hindi dictionary to the database.

Professor Amba Kulkarni's group at the University of Hyderabad has published a
digitized version of Apte's Sanskrit-Hindi dictionary, which is available from
their main GitHub repo (https://github.com/samsaadhanii/scl). But since the
repo as a whole is quite large (>250 MiB even with `--depth 1`), we download
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
    "m",
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
URL_TEMPLATE = (
    "https://github.com/samsaadhanii/scl/raw/master/MT/data/hi/Apte_dict/{letter}.xml"
)


def _make_key(xml: ET.Element) -> str:
    """Create a standardized lookup key for this entry.

    Steps:
    1. Convert the dictionary key to SLP1, which is our convention for
       dictionary lookup keys.
    2. Standardize the key's spelling using `standardize_key`.

    :param xml: the dictionary entry to proecss.
    """
    assert xml.tag in {"lexhead", "segmenthd"}, xml.tag
    key = xml.find("./dentry").text
    assert key

    key = sanscript.transliterate(key, sanscript.DEVANAGARI, sanscript.SLP1)
    key = standardize_key(key)
    return key


def _make_value(xml: ET.Element) -> str:
    """Serialize the given XML entry to a Unicode string.

    ElementTree's default serialization will escape most Unicode characters and
    create an unsightly output. Instead, just produce a simple Unicode `str`.
    """
    return ET.tostring(xml, encoding="utf-8").decode("utf-8")


def _make_entries(xml: ET.Element) -> Iterator[tuple[str, str]]:
    """Yield all entries in the given XML element.

    An element might contain multiple elements. This function first yields the
    parent (root) element then yields all children in order.

    :param xml: a `lexhead` element
    """
    assert xml.tag == "lexhead"
    children = xml.findall("./segmenthd")

    for child in children:
        # Remove this child so that it's not included in the parent entry.
        # (This is the standard we follow in other dictionary entries. In
        # the future, we can improve how we model sub-entries and make this
        # behavior a user preference.)
        xml.remove(child)

    # Yield the main entry.
    # (We yield the main element first to better support a potential use case
    # where we show in-order dictionary entries to the user.)
    key = _make_key(xml)
    value = _make_value(xml)
    yield key, value

    # Yield sub-entries (e.g. compounds) if any exist.
    for child in children:
        key = _make_key(child)
        value = _make_value(child)
        yield key, value


def _iter_entries_as_xml(blobs: list[str]) -> Iterator[tuple[str, str]]:
    for blob in blobs:
        xml = ET.fromstring(blob)
        for entry in xml:
            yield from _make_entries(entry)


@click.command()
@click.option("--use-cache/--no-use-cache", default=False)
def run(use_cache):
    print("Initializing database ...")
    engine = create_db()

    print(f"Fetching data from GitHub (use_cache = {use_cache})...")

    blobs = []
    for letter in LETTERS:
        url = URL_TEMPLATE.format(letter=letter)
        print(f"- Loading {letter} ({url})")
        blob = fetch_text(url, read_from_cache=use_cache)
        blobs.append(blob)

    create_from_scratch(
        engine,
        slug="apte-sh",
        title="आप्टे संस्कृत-हिन्दी कोश (1966)",
        generator=_iter_entries_as_xml(blobs),
    )


if __name__ == "__main__":
    run()
