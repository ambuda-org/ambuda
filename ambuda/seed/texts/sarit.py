"""Parse Sanskrit texts from SARIT.

"""
from ambuda.seed.texts.gretil import *


REPO = "https://github.com/sarit/SARIT-corpus.git"
BRANCH = "master"
PROJECT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-sarit"

ALLOW = [Spec("skandapuranam", "skandapurANam", "skandapurana.xml")]


def run():
    log("Downloading the latest data ...")
    fetch_latest_data(REPO, BRANCH, DATA_DIR)

    log("Initializing database ...")
    engine = create_db()

    for spec in ALLOW:
        add_document(engine, DATA_DIR, spec)
    log("Done.")


if __name__ == "__main__":
    run()
