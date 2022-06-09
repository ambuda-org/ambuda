"""Parse Sanskrit texts from GRETIL.

The GRETIL TEI format has some systematic inconsistencies. Instead of using it,
just process teh plain text.
"""
import io
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript
from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.seed.common import create_db, fetch_bytes, delete_existing_text


ZIP_URL = "http://gretil.sub.uni-goettingen.de/gretil/1_sanskr.zip"


@dataclass
class Spec:
    slug: str
    title: str
    filename: str


ALLOW = [
    Spec("kumarasambhavam", "kumArasambhavam", "sa_kAlidAsa-kumArasaMbhava.txt"),
    Spec("raghuvamsha", "raghuvaMzaH", "sa_kAlidAsa-raghuvaMza.txt"),
    Spec("kiratarjuniyam", "kirAtArjunIyam", "sa_bhAravi-kirAtArjunIya.txt"),
    Spec("shishupalavadham", "zizupAlavadham", "sa_mAgha-zizupAlavadha.txt"),
    Spec("rtusamhara", "RtusaMhAraH", "sa_kAlidAsa-RtusaMhAra.txt"),
    # Skip Bhattikavyam -- severe problems, needs extra processing
    # Spec("agnipurana", "agnipurANam", "sa_agnipurANa.txt"),
    # Spec("bhagavatapurana", "zrImadbhAgavatapurANam", "sa_bhAgavatapurANa.txt"),
]


XML_ID_KEY = "{http://www.w3.org/XML/1998/namespace}id"
NS = {
    "xml": "http://www.w3.org/XML/1998/namespace",
    "tei": "http://www.tei-c.org/ns/1.0",
    "": "http://www.tei-c.org/ns/1.0",
}


def log(*a):
    print(*a)


def iter_gretil_tei_docs() -> tuple[Spec, str]:
    zip_bytes = fetch_bytes(ZIP_URL)
    allowed_files = {x.filename: x for x in ALLOW}

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as ref:
        for item in ref.namelist():
            # Skip all non-TEI files.
            if not item.startswith("1_sanskr/tei/transformations/plaintext"):
                continue

            # For now, process only a shortlist of texts whose syntax
            # we can safely support.
            _, _, suffix = item.rpartition("/")
            if suffix not in allowed_files:
                continue

            spec = allowed_files[suffix]
            with ref.open(item) as f:
                yield spec, f.read().decode("utf-8")


def iter_lines(blob: str):
    started = False
    for line in blob.splitlines():
        if line == "# Text":
            started = True
            continue
        if started:
            # Mistake: two lines treated as one.
            # Fix: yield two separate lines
            if " / " in line and " // " in line:
                lines = line.split(" / ")
                assert len(lines) == 2
                yield lines[0] + " /"
                yield lines[1]
            else:
                yield line.strip()


def iter_blocks(lines):
    buf = []
    for line in lines:
        if line:
            buf.append(line.strip())
        elif buf:
            yield buf
            buf = []
    if buf:
        yield buf


def iter_sections(blocks):
    parsed = {}
    for block in blocks:
        last_line = block[-1]

        # Skip spurious verses.
        if last_line.endswith("*"):
            continue

        # Skip spurious text.
        if "//" not in last_line:
            log(f"  [unknown text]: {last_line}")
            continue

        assert len(block) <= 3, block
        first, last = block[0], block[-1]

        # Format first half
        if not first.endswith("|"):
            first += " |"

        # Format second half
        last = last.replace("//", "||")
        last_text, _, code = last.partition("||")
        text_id, block_id = code.split("_")
        chapter, n = block_id.split(".")

        last = f"{last_text}||{n}||"

        if chapter not in parsed:
            parsed[chapter] = []

        block[0] = first
        block[-1] = last
        parsed[chapter].append(block)

    for key, blocks in parsed.items():
        buf = ["<div>\n"]
        for b in blocks:
            buf.append("  <lg>\n")
            for L in b:
                hk = sanscript.transliterate(L, sanscript.IAST, sanscript.HK)
                buf.append(f"    <l>{hk}</l>")
            buf.append("  </lg>\n")
        buf.append("</div>")
        yield "".join(buf)


def parse_plain_text(blob: str):
    lines = iter_lines(blob)
    blocks = iter_blocks(lines)
    sections = iter_sections(blocks)
    return sections


def add_text(engine, spec: Spec, blob: str):
    log(f"Writing text: {spec.slug}")
    sections = parse_plain_text(blob)

    delete_existing_text(engine, spec.slug)
    with Session(engine) as session:
        text = db.Text(slug=spec.slug, title=spec.title)
        session.add(text)
        session.flush()

        text_id = text.id
        for i, xml in enumerate(sections):
            slug = str(i + 1)
            section = db.TextSection(text=text, slug=slug, title=slug, xml=xml)
            session.add(section)

        session.commit()


def run():
    log("Initializing database ...")
    engine = create_db()

    log("Fetching GRETIL data ...")
    for spec, blob in iter_gretil_tei_docs():
        add_text(engine, spec, blob)
    log("Done.")


if __name__ == "__main__":
    run()
