#!/usr/bin/env python3
"""Add the Amarakosha to the database."""

import re
from typing import Iterator

import click
from indic_transliteration import sanscript

from ambuda.seed.utils.cdsl_utils import create_from_scratch
from ambuda.seed.utils.data_utils import create_db, fetch_text
from ambuda.utils.dict_utils import standardize_key

RAW_URL = "https://raw.githubusercontent.com/indic-dict/stardict-sanskrit/master/sa-head/sa-entries/amara-onto/amara-onto.babylon"


def _create_entries(deva_key: str, body: str) -> Iterator[tuple[str, str]]:
    if "_" in deva_key:
        print(f"  bad key: {deva_key}")
        buf = []
        return

    assert "|" not in deva_key

    lines = [x.strip() for x in body.split("<br><br>")]
    key_and_lex, meaning, synonyms, citation, verse = lines[:5]
    lex_key, lex = key_and_lex.split()
    assert deva_key == lex_key

    key = sanscript.transliterate(deva_key, sanscript.DEVANAGARI, sanscript.SLP1)
    lex = lex.replace("।", "॰")
    synonyms = synonyms.replace(",", ", ").replace(":", " — ")

    verse = verse.replace(".।", "॥")
    verse = verse.replace("॥", " ॥")
    verse_xml_fragment = re.sub("।\s*", " ।</l><l>", verse)

    entry = "".join(
        [
            f"<body><s>",
            f"<p>{deva_key} <lex>{lex}</lex> {meaning}। {synonyms}।</p><lb/>",
            f"<quote><lg><l>{verse_xml_fragment}</l></lg><lb/>"
            f"<cite>{citation}</cite></quote></s></body>",
        ]
    )
    yield key, entry


def amara_generator(dict_blob: str) -> Iterator[tuple[str, str]]:
    buf = []
    for line in dict_blob.splitlines():
        if line.startswith("#"):
            continue

        line = line.strip()
        if line:
            buf.append(line)
        elif buf:
            key, body = buf
            yield from _create_entries(key, body)
            buf = []
    if buf:
        key, body = buf
        yield from _create_entries(key, body)


@click.command()
@click.option("--use-cache/--no-use-cache", default=False)
def run(use_cache):
    print("Initializing database ...")
    engine = create_db()

    print(f"Fetching data from GitHub (use_cache = {use_cache})...")
    text_blob = fetch_text(RAW_URL, read_from_cache=use_cache)

    print("Adding items to database ...")
    create_from_scratch(
        engine,
        slug="amara",
        title="अमरकोशः",
        generator=amara_generator(text_blob),
    )

    print("Done.")


if __name__ == "__main__":
    run()
