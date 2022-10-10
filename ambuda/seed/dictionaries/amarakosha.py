#!/usr/bin/env python3
"""Add the Amarakosha to the database.

Our input data file is a stardict file, which prints entries in a simple file
format:

    <key1>
    <value1>

    <key2>
    <value2>

    [...]

where each `value` is on a single line.
"""

import re
from typing import Iterator

import click
from indic_transliteration import sanscript

from ambuda.seed.utils.cdsl_utils import create_from_scratch
from ambuda.seed.utils.data_utils import create_db, fetch_text
from ambuda.utils.dict_utils import standardize_key

RAW_URL = "https://raw.githubusercontent.com/indic-dict/stardict-sanskrit/master/sa-head/sa-entries/amara-onto/amara-onto.babylon"


def create_entries(deva_key: str, body: str) -> Iterator[tuple[str, str]]:
    """For the given startdict, yield at most one entry.

    We use `yield` because this simplifies our calling logic. Callers can simply
    use `yield from ...` to yield data if it's present.
    """
    if "_" in deva_key:
        print(f"  bad key: {deva_key}")
        return

    # In other stardict files, "|" separates multiple key words. So, check that
    # we have exactly one here.
    assert "|" not in deva_key

    # In the input files, separate lines are consistently separated with a
    # double <br>.
    lines = [x.strip() for x in body.split("<br><br>")]
    # There are other fields here, but these five are most essential.
    key_and_lex, meaning, synonyms, citation, verse = lines[:5]
    lex_key, lex = key_and_lex.split()
    assert deva_key == lex_key

    # Create a standardized lookup key.
    key = sanscript.transliterate(deva_key, sanscript.DEVANAGARI, sanscript.SLP1)
    key = standardize_key(key)

    # The lexical data uses the danda to abbreviate the entry. Instead, use the
    # lāghava, which is more appropriate.
    lex = lex.replace("।", "॰")

    # Improve the display of synomym and verse data.
    synonyms = synonyms.replace(",", ", ").replace(":", " — ")
    verse = verse.replace(".।", "॥")
    verse = verse.replace("॥", " ॥")

    # Reshape data to XML, which we can interpret at serving time.
    verse_xml_fragment = re.sub(r"।\s*", " ।</l><l>", verse)
    entry = "".join(
        [
            "<body><s>",
            f"<p>{deva_key} <lex>{lex}</lex> {meaning}। {synonyms}।</p><lb/>",
            f"<quote><lg><l>{verse_xml_fragment}</l></lg><lb/>"
            f"<cite>{citation}</cite></quote></s></body>",
        ]
    )
    yield key, entry


def amara_generator(dict_blob: str) -> Iterator[tuple[str, str]]:
    """Iterate over all entries in the dictionary.

    :param dict_blob: the full dictionary string.
    """
    buf = []
    for line in dict_blob.splitlines():
        # Ignore comments.
        if line.startswith("#"):
            continue

        line = line.strip()
        if line:
            buf.append(line)
        elif buf:
            key, body = buf
            yield from create_entries(key, body)
            buf = []
    if buf:
        key, body = buf
        yield from create_entries(key, body)


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
