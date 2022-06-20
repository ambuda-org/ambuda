"""Parse Sanskrit texts from GRETIL.

The GRETIL TEI format has some systematic inconsistencies. Instead of using it,
just process teh plain text.
"""
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript
from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.seed.utils.itihasa_utils import create_db, delete_existing_text


@dataclass
class Spec:
    slug: str
    title: str
    filename: str


PROJECT_DIR = Path(__file__).resolve().parents[3]
GRETIL_DIR = PROJECT_DIR / "third-party-data" / "gretil"
ALLOW = [
    Spec("kumarasambhavam", "kumArasambhavam", "sa_kAlidAsa-kumArasaMbhava.xml"),
    Spec("raghuvamsham", "raghuvaMzam", "sa_kAlidAsa-raghuvaMza.xml"),
    Spec("kiratarjuniyam", "kirAtArjunIyam", "sa_bhAravi-kirAtArjunIya.xml"),
    Spec("shishupalavadham", "zizupAlavadham", "sa_mAgha-zizupAlavadha.xml"),
    Spec("rtusamharam", "RtusaMhAram", "sa_kAlidAsa-RtusaMhAra.xml"),
    Spec("shatakatrayam", "zatakatrayam", "sa_bhatRhari-zatakatraya.xml"),
    Spec("bhattikavyam", "bhaTTikAvyam", "sa_bhaTTi-rAvaNavadha.xml"),
    # Spec("agnipurana", "agnipurANam", "sa_agnipurANa.xml"),
    # Spec("bhagavatapurana", "zrImadbhAgavatapurANam", "sa_bhAgavatapurANa.xml"),
]


XML_ID_KEY = "{http://www.w3.org/XML/1998/namespace}id"
NS = {
    "xml": "http://www.w3.org/XML/1998/namespace",
    "tei": "http://www.tei-c.org/ns/1.0",
    "": "http://www.tei-c.org/ns/1.0",
}


@dataclass
class Block:
    slug: str
    blob: str


@dataclass
class Section:
    slug: str
    blocks: list[Block]


def log(*a):
    print(*a)


def remove_namespace(xml, prefix):
    for el in xml.iter("*"):
        if el.tag.startswith(prefix):
            el.tag = el.tag[len(prefix) :]


def to_slp1(xml):
    """Transliterate inline elements."""
    t = sanscript.transliterate
    for el in xml.iter("*"):
        if el.text:
            el.text = t(el.text, sanscript.IAST, sanscript.DEVANAGARI)
        if el.tail:
            el.tail = t(el.tail, sanscript.IAST, sanscript.DEVANAGARI)


def delete_unused_elems(xml):
    for L in xml.iter("l"):
        for el in L:
            if el.tag in {"seg", "hi"}:
                el.tag = None
            if el.tag in {"note"}:
                el.tag = None
                el.clear()
        text = "".join(L.itertext())
        text = text.replace("-", "")
        L.clear()
        L.text = text


def iter_sections(path: Path):
    xml = ET.parse(path).getroot()
    remove_namespace(xml, "{" + NS["tei"] + "}")

    body = xml.find("./text/body")
    delete_unused_elems(xml)
    to_slp1(body)

    n = 1
    for section_slug, div in enumerate(body.findall("./div")):
        section = Section(slug=(section_slug + 1), blocks=[])

        for child in div:
            if child.tag in {"note"}:
                continue

            assert child.tag in {"lg", "head", "p"}, child.tag
            if child.tag == "head":
                block_slug = "head"
            else:
                block_slug = str(n)
                n += 1

            blob = ET.tostring(child, encoding="utf-8").decode("utf-8")
            block = Block(slug=block_slug, blob=blob)
            section.blocks.append(block)

        yield section


def add_text(engine, spec: Spec):
    log(f"Writing text: {spec.slug}")
    path = GRETIL_DIR / spec.filename

    delete_existing_text(engine, spec.slug)
    with Session(engine) as session:
        text = db.Text(slug=spec.slug, title=spec.title)
        session.add(text)
        session.flush()

        n = 1
        for section in iter_sections(path):
            db_section = db.TextSection(
                text_id=text.id, slug=section.slug, title=section.slug
            )
            session.add(db_section)
            session.flush()

            for block in section.blocks:
                db_block = db.TextBlock(
                    text_id=text.id,
                    section_id=db_section.id,
                    slug=block.slug,
                    xml=block.blob,
                    n=n,
                )
                session.add(db_block)
                session.flush()
                n += 1

        session.commit()


def run():
    log("Initializing database ...")
    engine = create_db()

    for spec in ALLOW:
        add_text(engine, spec)
    log("Done.")


if __name__ == "__main__":
    run()
