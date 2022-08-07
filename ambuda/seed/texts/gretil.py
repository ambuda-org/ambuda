"""Parse Sanskrit texts from GRETIL.

The GRETIL TEI format has some systematic inconsistencies. Instead of using it,
just process teh plain text.
"""
import subprocess
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


REPO = "https://github.com/ambuda-project/gretil.git"
PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-gretil"
#: Slug to use for texts that have only one section.
SINGLE_SECTION_SLUG = "all"

ALLOW = [
    Spec("amarushatakam", "amaruzakatam", "sa_amaru-amaruzataka.xml"),
    Spec("kumarasambhavam", "kumArasambhavam", "sa_kAlidAsa-kumArasaMbhava.xml"),
    Spec("raghuvamsham", "raghuvaMzam", "sa_kAlidAsa-raghuvaMza.xml"),
    Spec("kiratarjuniyam", "kirAtArjunIyam", "sa_bhAravi-kirAtArjunIya.xml"),
    Spec("shishupalavadham", "zizupAlavadham", "sa_mAgha-zizupAlavadha.xml"),
    Spec("rtusamharam", "RtusaMhAram", "sa_kAlidAsa-RtusaMhAra.xml"),
    Spec("shatakatrayam", "zatakatrayam", "sa_bhatRhari-zatakatraya.xml"),
    Spec("bhattikavyam", "bhaTTikAvyam", "sa_bhaTTi-rAvaNavadha.xml"),
    Spec("meghadutam-kale", "meghadUtam", "sa_kAlidAsa-meghadUta-edkale.xml"),
    Spec("kokilasandesha", "kokilasaMdezaH", "sa_uddaNDa-kokilasaMdesa.xml"),
    Spec("bodhicaryavatara", "bodhicAryAvatAraH", "sa_zAntideva-bodhicaryAvatAra.xml"),
    Spec(
        "saundaranandam", "saundaranandam", "sa_azvaghoSa-saundarAnanda-edmatsunami.xml"
    ),
    Spec("caurapancashika", "caurapaJcAzikA", "sa_bilhaNa-caurapaJcAzikA.xml"),
    Spec("hamsadutam", "haMsadUtam", "sa_rUpagosvAmin-haMsadUta.xml"),
    Spec("mukundamala", "mukundamAlA", "sa_kulazekhara-mukundamAlA-eddurgaprasad.xml"),
]


XML_ID_KEY = "{http://www.w3.org/XML/1998/namespace}id"
NS = {
    "xml": "http://www.w3.org/XML/1998/namespace",
    "tei": "http://www.tei-c.org/ns/1.0",
    "": "http://www.tei-c.org/ns/1.0",
}


def fetch_latest_data(repo: str, data_dir: str):
    """Fetch the latest data from our GitHub repo."""
    if not data_dir.exists():
        subprocess.run(f"mkdir -p {data_dir}", shell=True)
        subprocess.run(f"git clone --branch=main {repo} {data_dir}", shell=True)

    subprocess.call("git fetch origin", shell=True, cwd=data_dir)
    subprocess.call("git checkout main", shell=True, cwd=data_dir)
    subprocess.call("git reset --hard origin/main", shell=True, cwd=data_dir)


@dataclass
class Block:
    slug: str
    #: XML blob.
    blob: str


@dataclass
class Section:
    slug: str
    blocks: list[Block]


@dataclass
class Document:
    #: <teiHeader> XML blob.
    header: str
    sections: list[Section]


def log(*a):
    print(*a)


def remove_namespace(xml: ET.Element, prefix: str):
    """Remove the given namespace prefix from all elements.

    ElementTree expands tidy namespaced names like "xml:id" into names like
    "{http://www.w3.org/XML/1998/namespace}id", which are less usable. This
    function removes these namespaces so that downstream code can be more
    readable.
    """
    for el in xml.iter("*"):
        if el.tag.startswith(prefix):
            el.tag = el.tag[len(prefix) :]


def to_slp1(xml: ET.Element):
    """Transliterate inline elements."""
    t = sanscript.transliterate
    for el in xml.iter("*"):
        if el.text:
            el.text = t(el.text, sanscript.IAST, sanscript.DEVANAGARI)
        if el.tail:
            el.tail = t(el.tail, sanscript.IAST, sanscript.DEVANAGARI)


def delete_unused_elements(xml: ET.Element):
    """Remove unused elements in-place."""
    for L in xml.iter("l"):
        for el in L:
            # Delete tag, keep text
            if el.tag in {"seg", "hi"}:
                el.tag = None
            # Delete tag and text.
            if el.tag in {"note"}:
                el.tag = None
                el.clear()
        text = "".join(L.itertext())
        text = text.replace("-", "")
        L.clear()
        L.text = text


def _make_section(xml: ET.Element, section_slug: str) -> Section:
    section = Section(slug=section_slug, blocks=[])
    n = 1
    for child in xml:
        # Skip these elements entirely.
        if child.tag in {"note", "del"}:
            continue

        assert child.tag in {"lg", "head", "p", "trailer", "milestone", "pb"}, child.tag
        if child.tag == "head":
            block_slug = "head"
        else:
            block_slug = str(n)
            n += 1

        blob = ET.tostring(child, encoding="utf-8").decode("utf-8")
        if section_slug == SINGLE_SECTION_SLUG:
            slug = block_slug
        else:
            slug = f"{section_slug}.{block_slug}"
        block = Block(slug=slug, blob=blob)
        section.blocks.append(block)

    return section


def parse_sections(xml: ET.Element) -> list[Section]:
    body = xml.find("./text/body")
    delete_unused_elements(xml)
    to_slp1(body)

    sections = []
    divs = body.findall("./div")
    if divs:
        # Text has one or more sections.
        for i, div in enumerate(body.findall("./div")):
            section_slug = str(i + 1)
            section = _make_section(div, section_slug)
            sections.append(section)
    else:
        # Text has exactly one section.
        section = _make_section(body, SINGLE_SECTION_SLUG)
        sections = [section]
    return sections


def parse_tei_document(xml: ET.Element) -> Document:
    remove_namespace(xml, "{" + NS["tei"] + "}")

    header = xml.find("./teiHeader")
    assert header
    header_blob = ET.tostring(header, encoding="utf-8").decode("utf-8")

    sections = parse_sections(xml)
    assert sections

    return Document(header=header_blob, sections=sections)


def add_document(engine, data_dir: str, spec: Spec):
    log(f"Writing text: {spec.slug}")
    document_path = data_dir / spec.filename

    delete_existing_text(engine, spec.slug)
    with Session(engine) as session:
        xml = ET.parse(document_path).getroot()
        document = parse_tei_document(xml)

        text = db.Text(slug=spec.slug, title=spec.title, header=document.header)
        session.add(text)
        session.flush()
        n = 1
        for section in document.sections:
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
                n += 1

        session.commit()


def run():
    log("Downloading the latest data ...")
    fetch_latest_data(REPO, DATA_DIR)

    log("Initializing database ...")
    engine = create_db()

    for spec in ALLOW:
        add_document(engine, DATA_DIR / "1_sanskr" / "tei", spec)
    log("Done.")


if __name__ == "__main__":
    run()
