import subprocess
import time
from pathlib import Path

import fitz
from slugify import slugify
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks import app
from config import create_config_only_app


class TaskStatus:
    """Helper class to track progress on the current task."""

    def __init__(self, task):
        self.task = task

    def update(self, current: int, total: int):
        """Update a progress bar for this task.

        :param current: progress numerator
        :param total: progress denominator
        """
        state = "PROGRESS" if current < total else "SUCCESS"
        self.task.update_state(state=state, meta={"current": current, "total": total})


def _split_pdf_into_pages(
    pdf_path: Path, output_dir: Path, task_status: TaskStatus
) -> int:
    """Split the given PDF into N JPEG images, one image per page.

    :param pdf_path: filesystem path to the PDF we should process.
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


def _add_project_to_database(title: str, pages_dir: Path, num_pages: int):
    session = q.get_session()
    slug = slugify(title)

    # Tasks must be idempotent -- clean up any prior state from an old run.
    print(f"Deleting old state ...")
    session.query(db.Project).filter_by(slug=slug).delete()
    session.commit()

    print(f"Creating project (slug = {slug})...")
    q.create_project(title=title, slug=slug)

    print(f"Fetching project and status ...")
    project = q.project(slug)
    unreviewed = session.query(db.PageStatus).filter_by(name="reviewed-0").one()

    for n in range(1, num_pages + 1):
        print(f"Creating page {n}")
        session.add(
            db.Page(
                project_id=project.id,
                slug=str(n),
                order=n,
                status_id=unreviewed.id,
            )
        )
    session.commit()
    print("Done.")


@app.task(bind=True)
def create_project(
    self, title: str, pdf_path: str, output_dir: str, app_environment: str
):
    print(f"Received task {title} on path {pdf_path}")
    pdf_path = Path(pdf_path)
    pages_dir = Path(output_dir)
    task_status = TaskStatus(self)

    num_pages = _split_pdf_into_pages(Path(pdf_path), Path(pages_dir), task_status)
    app = create_config_only_app(app_environment)
    with app.app_context():
        _add_project_to_database(title, pages_dir, num_pages)
