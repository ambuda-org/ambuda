#!/usr/bin/env python3
"""Convert the raw Ramayana text to XML."""


import json
import re
from dataclasses import dataclass
from pathlib import Path

import requests


BASE_URL = "https://bombay.indology.info/ramayana/text/ASCII/Ram0{n}.txt"


@dataclass
class Line:
    kanda: int
    section: int
    verse: int
    pada: str
    text: str


@dataclass
class Verse:
    kanda: int
    section: int
    n: int
    lines: list[Line]


@dataclass
class Section:
    kanda: int
    n: int
    verses: list[Verse]


@dataclass
class Kanda:
    n: int
    sections: list[Section]


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

        text = text.replace(';', '')

        yield Line(
            kanda=int(kanda),
            section=int(section),
            verse=int(verse),
            pada=pada,
            text=text,
        )


def iter_verses(raw: str):
    lines = list(iter_lines(raw))
    group = {}
    for L in lines:
        key = (L.kanda, L.section, L.verse)
        if key not in group:
            group[key] = []
        group[key].append(L)

    for lines in group.values():
        L = lines[0]
        yield Verse(kanda=L.kanda, section=L.section, n=L.verse, lines=lines)


def iter_sections(raw: str):
    verses = list(iter_verses(raw))
    group = {}
    for v in verses:
        key = (v.kanda, v.section)
        if key not in group:
            group[key] = []
        group[key].append(v)

    for verses in group.values():
        v = verses[0]
        yield Section(kanda=v.kanda, n=v.section, verses=verses)


def parse_kanda(raw: str) -> Kanda:
    sections = list(iter_sections(raw))
    first = sections[0]
    return Kanda(n=sections[0].kanda, sections=sections)


def write_section_xml(section, out_file):
    with open(out_file, "w") as f:
        f.write("<section>\n")
        for verse in section.verses:
            f.write("  <lg>\n")
            for i, line in enumerate(verse.lines):
                is_last = i == len(verse.lines) - 1
                if is_last:
                    f.write(f"    <l>{line.text} || {line.verse} ||</l>\n")
                else:
                    f.write(f"    <l>{line.text} |</l>\n")
            f.write("  </lg>\n")
        f.write("</section>\n")


def write_metadata(kandas: list[Kanda], out_file):
    sections = []
    for kanda in kandas:
        for section in kanda.sections:
            sections.append(
                {
                    "title": f"{section.kanda}.{section.n}",
                    "slug": f"{section.kanda}.{section.n}",
                }
            )
    metadata = {
        "title": "rAmAyaNam",
        "slug": "ramayana",
        "sections": sections,
    }
    with open(out_file, "w") as f:
        json.dump(metadata, f, indent=2)


def run():
    project_dir = Path(__file__).parent.parent
    output_dir = project_dir / "texts" / "ramayana"

    kandas = []
    for n in "1234567":
        url = BASE_URL.format(n=n)
        resp = requests.get(url)
        text = resp.text

        kanda = parse_kanda(text)
        for section in kanda.sections:
            outfile = output_dir / f"{section.kanda}.{section.n}.xml"
            write_section_xml(section, outfile)
            print(f"Wrote section to {outfile}.")
        kandas.append(kanda)

    metadata_path = output_dir / "index.json"
    write_metadata(kandas, metadata_path)
    print(f"Wrote metadata to {metadata_path}.")


if __name__ == "__main__":
    run()
