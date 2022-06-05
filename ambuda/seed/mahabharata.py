#!/usr/bin/env python3
"""Convert the raw Mahabharata text to XML."""


import re
from pathlib import Path

from sqlalchemy.orm import Session

from ambuda.database import Text, TextSection
from ambuda.seed.common import (
    Line,
    Kanda,
    delete_existing_text,
    fetch_text,
    get_verses,
    get_sections,
    get_section_xml,
    create_db,
)


PROJECT_DIR = Path(__file__).parent.parent.parent
BASE_URL = "https://bombay.indology.info/mahabharata/text/UD/MBh{n}.txt"


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

    return Kanda(n=sections[0].kanda, sections=sections)


def run():
    print("Initializing database ...")
    engine = create_db()

    print("Parsing text ...")
    kandas = []
    for n in range(1, 18 + 1):
        n = str(n)
        if len(n) == 1:
            n = "0" + n

        url = BASE_URL.format(n=n)
        text = fetch_text(url)
        kandas.append(parse_kanda(text))

    text_slug = "mahabharata"
    print("Cleaning up old state ...")
    delete_existing_text(engine, text_slug)

    print("Writing new data ...")
    with Session(engine) as session:
        text = Text(slug=text_slug, title="mahAbhAratam")
        session.add(text)
        session.flush()

        text_id = text.id
        items = []
        for kanda in kandas:
            for s in kanda.sections:
                slug = f"{s.kanda}.{s.n}"
                xml = get_section_xml(s)
                section = TextSection(text=text, slug=slug, title=slug, xml=xml)
                session.add(section)

        session.commit()
    print("Done.")


if __name__ == "__main__":
    run()
