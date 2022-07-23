import subprocess
from pathlib import Path

from sqlalchemy.orm import Session, load_only

import ambuda.database as db
from ambuda.seed.utils.itihasa_utils import create_db


REPO = "https://github.com/ambuda-project/dcs.git"
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-dcs"


def fetch_latest_data():
    """Fetch the latest data from the parse data repo."""
    if not DATA_DIR.exists():
        subprocess.run(f"mkdir -p {DATA_DIR}", shell=True)
        subprocess.run(f"git clone --branch=main {REPO} {DATA_DIR}", shell=True)

    subprocess.call("git fetch origin", shell=True, cwd=DATA_DIR)
    subprocess.call("git checkout main", shell=True, cwd=DATA_DIR)
    subprocess.call("git reset --hard origin/main", shell=True, cwd=DATA_DIR)


def drop_existing_parse_data(session, text_id: int):
    session.query(db.BlockParse).filter_by(text_id=text_id).delete()


def get_slug_id_map(session, text_id: int) -> dict[str, int]:
    """For each block, map its slug to its ID."""
    blocks = (
        session.query(db.TextBlock)
        .filter_by(text_id=text_id)
        .options(
            load_only(
                db.TextBlock.id,
                db.TextBlock.slug,
            )
        )
        .all()
    )
    return {b.slug: b.id for b in blocks}


def iter_parse_data(path: Path):
    block_slug = None
    buf = []
    with open(path) as f:
        for line in f:
            line = line.strip()

            if line.startswith("#"):
                comm, key, eq, value = line.split()
                if key == "id":
                    xml_id = value
                    _, _, block_slug = xml_id.partition(".")
            elif line:
                buf.append(line)
            else:
                yield block_slug, "\n".join(buf)
                buf = []
    if buf:
        yield block_slug, "\n".join(buf)


def add_parse_data(text_slug: str, path: Path):
    engine = create_db()

    with Session(engine) as session:
        text = session.query(db.Text).filter_by(slug=text_slug).first()
        drop_existing_parse_data(session, text.id)

        slug_id_map = get_slug_id_map(session, text.id)
        for slug, blob in iter_parse_data(path):
            session.add(
                db.BlockParse(text_id=text.id, block_id=slug_id_map[slug], data=blob)
            )
        session.commit()


def run():
    print("Fetching latest data ...")
    fetch_latest_data()

    for path in DATA_DIR.iterdir():
        if path.suffix == ".txt":
            print(f"Adding {path.stem} to the database ...")
            add_parse_data(path.stem, path)
    print("Done.")


if __name__ == "__main__":
    run()
