#!/usr/bin/env python3
"""Database utility functions."""


import hashlib
import io
from dataclasses import dataclass
from pathlib import Path
import zipfile

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import ambuda.database as db

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
    blocks: list[Verse]


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


def unzip_and_read(zip_bytes: bytes, filepath: str) -> str:
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as ref:
        with ref.open(filepath) as f:
            return f.read()


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
        yield Section(kanda=v.kanda, n=v.section, blocks=verses)


def get_verse_xml(verse, xml_id) -> str:
    buf = [f'<lg xml:id="{xml_id}">']
    for i, line in enumerate(verse.lines):
        is_last = i == len(verse.lines) - 1
        if is_last:
            buf.append(f"<l>{line.text} \u0965 {line.verse} \u0965</l>")
        else:
            buf.append(f"<l>{line.text} \u0964</l>")
    buf.append("</lg>")
    return "".join(buf)


def write_kandas(
    engine, kandas: list[Kanda], text_slug: str, text_title: str, xml_id_prefix: str
):
    with Session(engine) as session:
        text = db.Text(slug=text_slug, title=text_title)
        session.add(text)
        session.flush()

        text_id = text.id
        n = 1
        for kanda in kandas:
            for s in kanda.sections:
                section_slug = f"{s.kanda}.{s.n}"
                section = db.TextSection(
                    text_id=text_id, slug=section_slug, title=section_slug
                )
                session.add(section)
                session.flush()

                for block in s.blocks:
                    block_slug = f"{section_slug}.{block.n}"
                    xml_id = f"{xml_id_prefix}.{block_slug}"
                    block = db.TextBlock(
                        text_id=text_id,
                        section_id=section.id,
                        slug=block_slug,
                        xml=get_verse_xml(block, xml_id=xml_id),
                        n=n,
                    )
                    session.add(block)
                    n += 1
        session.commit()


def create_db():
    engine = create_engine(db.DATABASE_URI)
    db.Base.metadata.create_all(engine)
    return engine


def delete_existing_text(engine, slug: str):
    with Session(engine) as session:
        text = session.query(db.Text).where(db.Text.slug == slug).first()
        if text:
            session.delete(text)
            session.commit()
