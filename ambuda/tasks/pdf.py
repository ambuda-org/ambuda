import glob
import subprocess
from pathlib import Path

from slugify import slugify
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.queries import get_engine

command_template = (
    "gs -dNOPAUSE -sDEVICE=jpeg -r1260" " -sOutputFile={output_path} {filename} -c quit"
)


def create_pages(project_id: int, pdf_path: Path):
    """Split an uploaded PDF into individual pages.

    We need the PDF only so that we can create image pages.

    NOTE: this is a background task. Arguments must be JSON-serializable.
    TODO(arun): use celery/dramatiq for task scheduling

    :param project_id: db ID for the parent project
    :param pdf_path: path to the PDF file on disc.
    """
    session = Session(get_engine())

    # String interpolation is safe as long as pdf_path is safe.
    print("Splitting PDF pages.")
    output_path = str(pdf_path.parent / "%d.jpg")
    command = command_template.format(
        filename=pdf_path, output_path=output_path, num_threads=4
    )
    subprocess.run(command, shell=True)

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
