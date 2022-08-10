#!/usr/bin/env python3
"""Database utility functions."""


import hashlib
import io
import os
from dataclasses import dataclass
from pathlib import Path
import zipfile
from typing import Iterator

import requests
from dotenv import load_dotenv
from indic_transliteration import sanscript
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import config
import ambuda.database as db


load_dotenv()
PROJECT_DIR = Path(__file__).parent.parent.parent
CACHE_DIR = PROJECT_DIR / "data" / "download-cache"


@dataclass
class Line:
    """A line (half-verse) in a large text."""

    kanda: int
    section: int
    verse: int
    pada: str
    text: str


@dataclass
class Verse:
    """A verse in a large text."""

    kanda: int
    section: int
    n: int
    lines: list[Line]


@dataclass
class Section:
    """A subsection of a large text."""

    kanda: int
    n: int
    blocks: list[Verse]


@dataclass
class Kanda:
    """A subsection of a large text."""

    n: int
    sections: list[Section]


def fetch_text(url: str) -> str:
    """Fetch text data against a simple cache.

    In production, we don't need the cache at all. But during development, it's
    useful to use a cache so that we can iterate on the end-to-end setup without
    waiting on network overhead.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    resp = requests.get(url)
    path.write_text(resp.text)
    return resp.text


def fetch_bytes(url: str) -> bytes:
    """Fetch binary data against a simple cache.

    In production, we don't need the cache at all. But during development, it's
    useful to use a cache so that we can iterate on the end-to-end setup without
    waiting on network overhead.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    if path.exists():
        return path.read_bytes()
    else:
        resp = requests.get(url)
        path.write_bytes(resp.content)
        return resp.content


def unzip_and_read(zip_bytes: bytes, filepath: str) -> str:
    """Open a zip archive and read plain-text data from one of its files."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as ref:
        with ref.open(filepath) as f:
            return f.read()


def get_verses(lines) -> Iterator[Verse]:
    group = {}
    for L in lines:
        key = (L.kanda, L.section, L.verse)
        if key not in group:
            group[key] = []
        group[key].append(L)

    for lines in group.values():
        L = lines[0]
        yield Verse(kanda=L.kanda, section=L.section, n=L.verse, lines=lines)


def get_sections(verses) -> Iterator[Section]:
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
            num = sanscript.transliterate(
                str(line.verse), sanscript.HK, sanscript.DEVANAGARI
            )
            # Double danda
            buf.append(f"<l>{line.text} \u0965 {num} \u0965</l>")
        else:
            # Single danda
            buf.append(f"<l>{line.text} \u0964</l>")
    buf.append("</lg>")
    return "".join(buf)


def write_kandas(
    engine,
    kandas: list[Kanda],
    text_slug: str,
    text_title: str,
    tei_header: str,
    xml_id_prefix: str,
):
    with Session(engine) as session:
        text = db.Text(slug=text_slug, title=text_title, header=tei_header)
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
    flask_env = os.environ["FLASK_ENV"]
    conf = config.config[flask_env]
    engine = create_engine(conf.SQLALCHEMY_DATABASE_URI)

    db.Base.metadata.create_all(engine)
    return engine


def delete_existing_text(engine, slug: str):
    with Session(engine) as session:
        text = session.query(db.Text).where(db.Text.slug == slug).first()
        if text:
            session.delete(text)
            session.commit()
