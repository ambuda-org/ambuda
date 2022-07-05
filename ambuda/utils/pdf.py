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


def create_pages(session, project: db.Project, pdf_path: Path):
    """Split an uploaded PDF into individual pages.

    We need the PDF only so that we can create image pages.
    """
    # String interpolation is safe as long as pdf_path is safe.
    print("Splitting PDF pages.")
    output_path = str(pdf_path.parent / "%d.jpg")
    command = command_template.format(
        filename=pdf_path, output_path=output_path, num_threads=4
    )
    subprocess.run(command, shell=True)

    print("Committing ...")
    for path in sorted(pdf_path.parent.iterdir()):
        if path.suffix != ".jpg":
            continue

        order = int(path.stem)
        session.add(
            db.Page(
                project_id=project.id,
                slug=str(order),
                order=order,
                image_path=str(path),
            )
        )
    session.commit()
    print("Committed.")


def create_project(title: str, slug: str, pdf_path: Path):
    session = Session(get_engine())

    project = db.Project(slug=slug, title=title)
    session.add(project)
    session.commit()

    create_pages(session, project, pdf_path)
