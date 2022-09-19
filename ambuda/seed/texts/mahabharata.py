#!/usr/bin/env python3
"""Convert the raw Mahabharata text to XML."""


import re

import ambuda.seed.utils.data_utils
import ambuda.seed.utils.itihasa_utils as iti

BASE_URL = "https://bombay.indology.info/mahabharata/text/UD/MBh{n}.txt"

TEI_HEADER = """<teiHeader xml:lang="en">
  <fileDesc>
    <titleStmt>
        <title>Mahābhārata</title>
        <author>Vyāsa</author>
    </titleStmt>

    <publicationStmt>
        <publisher>bombay.indology.info</publisher>
        <availability>
        <p>The electronic text of the Mahābhārata is Copyright © The Bhandarkar
        Oriental Research Institute (BORI), Pune and is sourced from <ref target="http://bombay.indology.info/mahabharata/statement.html">John Smith's website.</ref></p>

        </availability>
    </publicationStmt>
  </fileDesc>
</teiHeader>
"""


def iter_lines(raw: str):
    for line in raw.splitlines():
        if line.startswith("%"):
            continue
        m = re.match(r"(\d\d)(\d\d\d)(\d\d\d)([aceA-Z]?) (.*)", line)
        assert m, f"Bad match: {line}"

        kanda = m.group(1)
        section = m.group(2)
        verse = m.group(3)
        pada = m.group(4)
        text = m.group(5)

        text = text.replace(";", "").replace("&", "&amp;")

        yield iti.Line(
            kanda=int(kanda),
            section=int(section),
            verse=int(verse),
            pada=pada,
            text=text,
        )


def parse_kanda(raw: str) -> iti.Kanda:
    lines = list(iter_lines(raw))
    verses = list(iti.get_verses(lines))
    sections = list(iti.get_sections(verses))
    return iti.Kanda(n=sections[0].kanda, sections=sections)


def run():
    text_slug = "mahabharatam"

    print("Initializing database ...")
    engine = ambuda.seed.utils.data_utils.create_db()

    print("Cleaning up old state ...")
    iti.delete_existing_text(engine, text_slug)

    print("Parsing text ...")
    kandas = []
    for n in range(1, 18 + 1):
        n = str(n)
        if len(n) == 1:
            n = "0" + n

        url = BASE_URL.format(n=n)
        text = ambuda.seed.utils.data_utils.fetch_text(url)
        kandas.append(parse_kanda(text))

    print("Writing text ...")
    iti.write_kandas(
        engine,
        kandas,
        text_slug=text_slug,
        text_title="mahAbhAratam",
        tei_header=TEI_HEADER,
        xml_id_prefix="MBh",
    )

    print("Done.")


if __name__ == "__main__":
    run()
