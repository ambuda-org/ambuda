import subprocess
from pathlib import Path

from sqlalchemy.orm import Session, load_only

import ambuda.database as db
from ambuda.seed.utils.data_utils import create_db

REPO = "https://github.com/ambuda-org/dcs.git"
PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / "data" / "ambuda-dcs"


class UpdateException(Exception):
    pass


def log(*a):
    print(*a)


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
                if line.count("\t") != 2:
                    raise ValueError(f'Line "{line}" must have exactly two tabs.')
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
        if not text:
            raise UpdateException()

        drop_existing_parse_data(session, text.id)

        slug_id_map = get_slug_id_map(session, text.id)
        for slug, blob in iter_parse_data(path):
            session.add(
                db.BlockParse(text_id=text.id, block_id=slug_id_map[slug], data=blob)
            )
        session.commit()


def run():
    log("Fetching latest data ...")
    fetch_latest_data()

    skipped = []
    for path in DATA_DIR.iterdir():
        if path.suffix == ".txt":
            try:
                add_parse_data(path.stem, path)
                log(f"- Added {path.stem} parse data to the database.")
            except UpdateException:
                log(f"- Skipped {path.stem}.")
                skipped.append(path.stem)

    log("Done.")

    if skipped:
        log("")
        log("The following texts were skipped because we couldn't find them")
        log("in the database:")
        for slug in skipped:
            log(f"- {slug}")
        log("")
        log("To add these texts, run the seed scripts in ambuda/seed/texts.")
        log("Note that the Ramayana and the Mahabharata have their own special")
        log("seed scripts.")


if __name__ == "__main__":
    run()
