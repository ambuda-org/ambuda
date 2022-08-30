"""Upload TEI documents from GRETIL."""

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

import ambuda.database as db
from ambuda.seed.utils.itihasa_utils import create_db
from ambuda.utils.tei_parser import parse_document, Document


@dataclass
class Spec:
    slug: str
    title: str
    filename: str


REPO = "https://github.com/ambuda-org/gretil.git"
PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-gretil"
#: Slug to use for texts that have only one section.

ALLOW = [
    Spec("amarushatakam", "amaruzatakam", "sa_amaru-amaruzataka.xml"),
    Spec("kumarasambhavam", "kumArasambhavam", "sa_kAlidAsa-kumArasaMbhava.xml"),
    Spec("raghuvamsham", "raghuvaMzam", "sa_kAlidAsa-raghuvaMza.xml"),
    Spec("kiratarjuniyam", "kirAtArjunIyam", "sa_bhAravi-kirAtArjunIya.xml"),
    Spec("shishupalavadham", "zizupAlavadham", "sa_mAgha-zizupAlavadha.xml"),
    Spec("rtusamharam", "RtusaMhAram", "sa_kAlidAsa-RtusaMhAra.xml"),
    Spec("shatakatrayam", "zatakatrayam", "sa_bhatRhari-zatakatraya.xml"),
    Spec("bhattikavyam", "bhaTTikAvyam", "sa_bhaTTi-rAvaNavadha.xml"),
    Spec("meghadutam-kale", "meghadUtam", "sa_kAlidAsa-meghadUta-edkale.xml"),
    Spec("kokilasandesha", "kokilasaMdezaH", "sa_uddaNDa-kokilasaMdesa.xml"),
    Spec("bodhicaryavatara", "bodhicaryAvatAraH", "sa_zAntideva-bodhicaryAvatAra.xml"),
    Spec(
        "saundaranandam", "saundaranandam", "sa_azvaghoSa-saundarAnanda-edmatsunami.xml"
    ),
    Spec("caurapancashika", "caurapaJcAzikA", "sa_bilhaNa-caurapaJcAzikA.xml"),
    Spec("hamsadutam", "haMsadUtam", "sa_rUpagosvAmin-haMsadUta.xml"),
    Spec("mukundamala", "mukundamAlA", "sa_kulazekhara-mukundamAlA-eddurgaprasad.xml"),
    Spec("shivopanishat", "zivopaniSat", "sa_zivopaniSad.xml"),
    Spec("catuhshloki", "catuHzlokI", "sa_yAmuna-catuHzlokI.xml"),
]


def log(*a):
    logging.info(*a)


def fetch_latest_data():
    """Fetch the latest data from our GitHub repo."""
    if not DATA_DIR.exists():
        subprocess.run(f"mkdir -p {DATA_DIR}", shell=True)
        subprocess.run(f"git clone --branch=main {REPO} {DATA_DIR}", shell=True)

    subprocess.call("git fetch origin", shell=True, cwd=DATA_DIR)
    subprocess.call("git checkout main", shell=True, cwd=DATA_DIR)
    subprocess.call("git reset --hard origin/main", shell=True, cwd=DATA_DIR)


def _create_new_text(session, spec: Spec, document: Document):
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


def add_document(engine, spec: Spec):
    document_path = DATA_DIR / "1_sanskr" / "tei" / spec.filename

    with Session(engine) as session:
        if session.query(db.Text).filter_by(slug=spec.slug).first():
            # FIXME: update existing texts in-place so that we can capture
            # changes. As a workaround for now, we can delete then re-create.
            log(f"- Skipped {spec.slug} (already exists)")
        else:
            document = parse_document(document_path)
            _create_new_text(session, spec, document)
            log(f"- Created {spec.slug}")


def run():
    logging.getLogger().setLevel(0)
    log("Downloading the latest data ...")
    fetch_latest_data()

    log("Initializing database ...")
    engine = create_db()

    for spec in ALLOW:
        add_document(engine, spec)
    log("Done.")


if __name__ == "__main__":
    run()
