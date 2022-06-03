#!/usr/bin/env python3
"""Convert the raw Ramayana text to XML."""


import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_DIR / ".cache"


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


def fetch_text(url: str) -> str:
    """Simple cache to avoid network overhead."""
    CACHE_DIR.mkdir(exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    if path.exists():
        return path.read_text()
    else:
        resp = requests.get(url)
        path.write_text(resp.text)
        return resp.text


def fetch_bytes(url: str) -> bytes:
    """Simple cache to avoid network overhead."""
    CACHE_DIR.mkdir(exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    if path.exists():
        return path.read_bytes()
    else:
        resp = requests.get(url)
        path.write_bytes(resp.content)
        return resp.content


@dataclass
class Kanda:
    n: int
    sections: list[Section]


def get_verses(lines):
    group = {}
    for L in lines:
        key = (L.kanda, L.section, L.verse)
        if key not in group:
            group[key] = []
        group[key].append(L)

    for lines in group.values():
        L = lines[0]
        yield Verse(kanda=L.kanda, section=L.section, n=L.verse, lines=lines)


def get_sections(verses):
    group = {}
    for v in verses:
        key = (v.kanda, v.section)
        if key not in group:
            group[key] = []
        group[key].append(v)

    for verses in group.values():
        v = verses[0]
        yield Section(kanda=v.kanda, n=v.section, verses=verses)


def write_section_xml(section, out_file):
    with open(out_file, "w") as f:
        f.write("<section>\n")
        for verse in section.verses:
            f.write("  <lg>\n")
            for i, line in enumerate(verse.lines):
                is_last = i == len(verse.lines) - 1
                if is_last:
                    f.write(f"    <l>{line.text} \u0965 {line.verse} \u0965</l>\n")
                else:
                    f.write(f"    <l>{line.text} \u0964</l>\n")
            f.write("  </lg>\n")
        f.write("</section>\n")


def write_metadata(title: str, slug: str, kandas: list[Kanda], out_file):
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
        "title": title,
        "slug": slug,
        "sections": sections,
    }
    with open(out_file, "w") as f:
        json.dump(metadata, f, indent=2)
