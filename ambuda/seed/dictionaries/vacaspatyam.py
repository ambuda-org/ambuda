#!/usr/bin/env python3
"""Add the Vacaspatyam to the database."""

import re

from ambuda.seed.utils.cdsl_utils import create_from_scratch, iter_entries_as_xml
from ambuda.seed.utils.data_utils import create_db, fetch_bytes, unzip_and_read
from ambuda.utils.dict_utils import standardize_key

ZIP_URL = (
    "https://www.sanskrit-lexicon.uni-koeln.de/scans/VCPScan/2020/downloads/vcpxml.zip"
)


def _make_text_blob(xml):
    body = xml.find("./body")

    # Add whitespace to each line by default. We'll strip it out if
    # the previous line has a hyphen.
    for lb in body.iter("lb"):
        lb.text = " "

    # vcp.xml has little useful structure, so we can discard it all.
    text = "".join(body.itertext())

    # Strip out page annotations.
    text = re.sub(r"\[Page.*?\]", "", text)

    # Soft hyphen -- allows web text to break here, but will otherwise render
    # text continuously.
    text = re.sub(r"\s*-\s*", "\u00ad", text)

    # Quotes -- generally noisy, so replace with regexes
    text = re.sub(r"\u201c(.*?)\u201d", r"<q>\1</q>", text)

    # Extract definition numbers and put each on their own lines
    buf = []
    n = 1
    tokens = text.split()
    for i, token in enumerate(tokens):
        if token == str(n) and (i < len(tokens) - 1 and tokens[i + 1] != "|"):
            buf.append(f"<lb/><b>{n}</b>")
            n += 1
        else:
            buf.append(token)
    text = " ".join(buf)

    # Use the degree sign for better readability.
    text = text.replace("0", "\u00b0")

    # Save as serialized XML
    return f"<body><s>{text}</s></body>"


def v_generator(xml_blob: str):
    for key, xml in iter_entries_as_xml(xml_blob):
        key = standardize_key(key)
        blob = _make_text_blob(xml)
        yield key, blob


def run():
    title="Vācaspatyam (1873)"

    print(f"Initializing {title} in database ...")
    engine = create_db()

    print(f"Fetching {title} data from CDSL ...")
    zip_bytes = fetch_bytes(ZIP_URL)
    xml_blob = unzip_and_read(zip_bytes, "xml/vcp.xml")

    print(f"Adding {title} items to database ...")
    create_from_scratch(
        engine,
        slug="vacaspatyam",
        title=title,
        generator=v_generator(xml_blob),
    )

    print("Done.")
    return True


if __name__ == "__main__":
    run()
