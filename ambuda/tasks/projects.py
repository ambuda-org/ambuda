import subprocess
import time
from pathlib import Path

from slugify import slugify
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.tasks import app
from ambuda.queries import get_engine

command_template = (
    "gs -dNOPAUSE -sDEVICE=jpeg -r1260" " -sOutputFile={output_path} {filename} -c quit"
)


def _split_pdf_into_pages(pdf_path: Path, output_dir: Path):
    output_path = output_dir / "%d.jpg"
    command = command_template.format(
        filename=pdf_path,
        output_path=output_path,
    )
    subprocess.run(command, shell=True)


def create_pages(project_id: int, pdf_path: Path):
    """Split an uploaded PDF into individual pages.

    We need the PDF only so that we can create image pages.

    NOTE: this is a background task. Arguments must be JSON-serializable.
    TODO(arun): use celery/dramatiq for task scheduling

    :param project_id: db ID for the parent project
    :param pdf_path: path to the PDF file on disc.
    """
    session = Session(get_engine())

    # Tasks must be idempotent -- clean up any prior state from an old run.
    assert project_id
    session.query(db.Page).filter_by(project_id=project_id).delete()
    session.commit()

    print("Committing ...")
    for path in sorted(pdf_path.parent.iterdir()):
        if path.suffix != ".jpg":
            continue

        order = int(path.stem)
        session.add(
            db.Page(
                project_id=project_id,
                slug=str(order),
                order=order,
                image_path=str(path),
            )
        )
    session.commit()
    print("Committed.")


@app.task(bind=True)
def create_project(self, title: str, pdf_path: str, output_dir: str, database_uri: str):
    print(f"Received task {title} on path {pdf_path}")
    _split_pdf_into_pages(Path(pdf_path), Path(output_dir))
    # self.update_state(state="PROGRESS", meta={"current": i, "total": 100})
    # self.update_state(state="SUCCESS")
    # _create_project(title, output_dir, database_uri)
