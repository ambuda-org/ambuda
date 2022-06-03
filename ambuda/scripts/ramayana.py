#!/usr/bin/env python3
"""Convert the raw Ramayana text to XML."""


import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests

from ambuda.scripts.common import (
    Line,
    Verse,
    Section,
    Kanda,
    get_verses,
    get_sections,
    fetch_text,
    write_section_xml,
    write_metadata,
)

PROJECT_DIR = Path(__file__).parent.parent.parent

BASE_URL = "https://bombay.indology.info/ramayana/text/UD/Ram{n}.txt"


def iter_lines(raw: str):
    for line in raw.splitlines():
        if line.startswith("%"):
            continue
        m = re.match(r"(\d)(\d\d\d)(\d\d\d)([aceg]) (.*)", line)
        assert m, f"Bad match: {line}"

        kanda = m.group(1)
        section = m.group(2)
        verse = m.group(3)
        pada = m.group(4)
        text = m.group(5)

        text = text.replace(";", "").replace("&", "&amp;")

        yield Line(
            kanda=int(kanda),
            section=int(section),
            verse=int(verse),
            pada=pada,
            text=text,
        )


def parse_kanda(raw: str) -> Kanda:
    lines = list(iter_lines(raw))
    verses = list(get_verses(lines))
    sections = list(get_sections(verses))

    first = sections[0]
    return Kanda(n=sections[0].kanda, sections=sections)


def run():
    output_dir = PROJECT_DIR / "texts" / "ramayana"

    kandas = []
    for n in range(1, 7 + 1):
        n = str(n)
        if len(n) == 1:
            n = "0" + n

        url = BASE_URL.format(n=n)
        text = fetch_text(url)

        kanda = parse_kanda(text)
        for section in kanda.sections:
            outfile = output_dir / f"{section.kanda}.{section.n}.xml"
            write_section_xml(section, outfile)
            print(f"Wrote section to {outfile}.")
        kandas.append(kanda)

    metadata_path = output_dir / "index.json"
    write_metadata("rAmAyaNam", "ramayana", kandas, metadata_path)
    print(f"Wrote metadata to {metadata_path}.")


if __name__ == "__main__":
    run()
