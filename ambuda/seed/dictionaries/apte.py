#!/usr/bin/env python3
"""Add the Apte (1890) dictionary to the database."""

import re
import xml.etree.ElementTree as ET

from ambuda.seed.utils import sandhi_utils
from ambuda.seed.utils.cdsl_utils import create_from_scratch, iter_entries_as_xml
from ambuda.seed.utils.data_utils import create_db, fetch_bytes, unzip_and_read
from ambuda.utils.dict_utils import standardize_key

ZIP_URL = "https://www.sanskrit-lexicon.uni-koeln.de/scans/AP90Scan/2020/downloads/ap90xml.zip"


def _delete_ab_pb(cur, prev):
    cur.tag = cur.text = None
    cur.text = None

    # Delete wrapping parens.
    assert prev.tail.endswith("(")
    assert cur.tail.startswith(")")
    prev.tail = prev.tail[:-1]
    cur.tail = cur.tail[1:]


def _delete_malformed_pb_annotations(xml):
    """Delete malformed page break annotations."""
    ab_parents = xml.findall(".//ab[.='pb']/..")
    for parent in ab_parents:
        for i, child in enumerate(parent):
            if child.tag == "ab" and child.text == "pb":
                prev = parent[i - 1]
                cur = parent[i]
                _delete_ab_pb(cur, prev)


def _trim_b_whitespace(xml):
    """Extra space found on various elements, e.g. <b> Comp.</b>"""
    for b in xml.findall(".//b"):
        b.text = b.text.strip()


def _transform_line_breaks(xml):
    """Use <lb> for line breaks to match MW conventions."""
    for div in xml.findall(".//div[@n='1']"):
        assert div.text is None
        div.tag = "lb"
        div.attrib = {}


def _make_compounds(first_word, groups):
    if first_word[-1] in "MH":
        first_word = first_word[:-1]

    for group in groups:
        child = group[0]
        # Case 1: simple and well-formed
        if re.fullmatch("\w+", child.text):
            samasa = sandhi_utils.apply(first_word, child.text)
            group[0].text = first_word + "\u2014" + group[0].text
            yield samasa, group

        # Case 2: other
        else:
            # I'll support this gradually, but there's too much noise in the data
            # right now.
            pass


def split_on(xs, fn):
    """Split a list of items on a predicate function."""
    buf = []
    for x in xs:
        if fn(x):
            if buf:
                yield buf
            buf = []
        else:
            buf.append(x)
    if buf:
        yield buf


def _explode_entries(xml):
    # TODO: investigate key2
    base_word = xml.find("./h/key1").text
    body = xml.find("./body")

    # First, yield the full entry with all compounds.
    # Once our compound parsing has ~100% coverage, we can trim this down.
    yield base_word, ET.tostring(body, encoding="utf-8")

    # Find elements after the "Comp." marker.
    comp_elements = None
    for i, child in enumerate(body):
        if child.tag == "b" and child.text == "Comp.":
            comp_elements = body[i + 1 :]
            break
    if not comp_elements:
        return

    # \u2014 is a long dash ('—') and marks a new entry.
    groups = list(
        split_on(comp_elements, lambda e: e.tag == "b" and e.text == "\u2014")
    )
    # The first group (before the first dash) is just junk (e.g. page break
    # elements) -- ignore.
    groups = groups[1:]

    for compound, elems in _make_compounds(base_word, groups):
        body[:] = elems
        yield compound, ET.tostring(body, encoding="utf-8")


def apte_generator(xml_blob: str):
    for _, xml in iter_entries_as_xml(xml_blob):
        _trim_b_whitespace(xml)
        _delete_malformed_pb_annotations(xml)
        _transform_line_breaks(xml)

        for raw_key, blob in _explode_entries(xml):
            standard_key = standardize_key(raw_key)
            yield standard_key, blob


def run():
    title="Apte Practical Sanskrit-English Dictionary (1890)"

    print(f"Initializing {title} in database ...")
    engine = create_db()
    
    print(f"Fetching {title} data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/ap90.xml")

    print(f"Adding {title} items to database ...")
    create_from_scratch(
        engine,
        slug="apte",
        title=title,
        generator=apte_generator(xml_blob),
    )

    print("Done.")
    return True


if __name__ == "__main__":
    run()
