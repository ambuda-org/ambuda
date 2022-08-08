import subprocess
import time
from pathlib import Path

import fitz
from slugify import slugify
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.queries import get_engine
from ambuda.tasks import app


class TaskStatus:
    """Helper class to track progress on the current task."""

    def __init__(self, task):
        self.task = task

    def update(self, current: int, total: int):
        """Update a progress bar for this task."""
        state = "PROGRESS" if current < total else "SUCCESS"
        self.task.update_state(state=state, meta={"current": current, "total": total})


def _split_pdf_into_pages(
    pdf_path: Path, output_dir: Path, task_status: TaskStatus
) -> int:
    """Split the given PDF into N JPEG images, one image per page.

    :param pdf_path:
    :param output_dir: the directory to which we'll write these images.
    """
    doc = fitz.open(pdf_path)
    task_status.update(0, doc.page_count)
    for page in doc:
        n = page.number + 1
        pix = page.get_pixmap(dpi=200)
        output_path = output_dir / f"{n}.jpg"
        pix.pil_save(output_path, optimize=True)
        task_status.update(n, doc.page_count)
    return doc.page_count


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
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    task_status = TaskStatus(self)

    num_pages = _split_pdf_into_pages(Path(pdf_path), Path(output_dir), task_status)
    # _add_project_to_database(title, output_dir, database_uri)
