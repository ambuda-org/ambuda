"""Upload TEI documents from GRETIL."""

import logging
import subprocess
from pathlib import Path

from ambuda.enums import TextGenre
from ambuda.seed.utils.data_utils import Spec, add_document, create_db

REPO = "https://github.com/ambuda-org/gretil.git"
PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-gretil"
#: Slug to use for texts that have only one section.

ALLOW = [
    Spec("amarushatakam", "amaruzatakam", "sa_amaru-amaruzataka.xml", TextGenre.KAVYA),
    Spec("kumarasambhavam", "kumArasambhavam", "sa_kAlidAsa-kumArasaMbhava.xml", TextGenre.KAVYA),
    Spec("raghuvamsham", "raghuvaMzam", "sa_kAlidAsa-raghuvaMza.xml", TextGenre.KAVYA),
    Spec("kiratarjuniyam", "kirAtArjunIyam", "sa_bhAravi-kirAtArjunIya.xml", TextGenre.KAVYA),
    Spec("shishupalavadham", "zizupAlavadham", "sa_mAgha-zizupAlavadha.xml", TextGenre.KAVYA),
    Spec("rtusamharam", "RtusaMhAram", "sa_kAlidAsa-RtusaMhAra.xml", TextGenre.KAVYA),
    Spec("shatakatrayam", "zatakatrayam", "sa_bhatRhari-zatakatraya.xml", TextGenre.KAVYA),
    Spec("bhattikavyam", "bhaTTikAvyam", "sa_bhaTTi-rAvaNavadha.xml", TextGenre.KAVYA),
    Spec("meghadutam-kale", "meghadUtam", "sa_kAlidAsa-meghadUta-edkale.xml", TextGenre.KAVYA),
    Spec("kokilasandesha", "kokilasaMdezaH", "sa_uddaNDa-kokilasaMdesa.xml", TextGenre.KAVYA),
    Spec("bodhicaryavatara", "bodhicaryAvatAraH", "sa_zAntideva-bodhicaryAvatAra.xml", TextGenre.ANYE),
    Spec(
        "saundaranandam", "saundaranandam", "sa_azvaghoSa-saundarAnanda-edmatsunami.xml", TextGenre.KAVYA
    ),
    Spec("caurapancashika", "caurapaJcAzikA", "sa_bilhaNa-caurapaJcAzikA.xml", TextGenre.KAVYA),
    Spec("hamsadutam", "haMsadUtam", "sa_rUpagosvAmin-haMsadUta.xml", TextGenre.KAVYA),
    Spec("mukundamala", "mukundamAlA", "sa_kulazekhara-mukundamAlA-eddurgaprasad.xml", TextGenre.KAVYA),
    Spec("shivopanishat", "zivopaniSat", "sa_zivopaniSad.xml", TextGenre.UPANISHAT),
    Spec("catuhshloki", "catuHzlokI", "sa_yAmuna-catuHzlokI.xml", TextGenre.ANYE),
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


def run():
    logging.getLogger().setLevel(0)
    log("Downloading the latest data ...")

    try:
        fetch_latest_data()

        log("Initializing database ...")
        engine = create_db()

        for spec in ALLOW:
            document_path = DATA_DIR / "1_sanskr" / "tei" / spec.filename
            add_document(engine, spec, document_path)
    except Exception as ex:
        raise Exception("Error: Failed to get latest from GRETIL.") from ex

    log("Done.")


if __name__ == "__main__":
    run()
