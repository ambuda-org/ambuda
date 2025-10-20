"""Background tasks for proofing projects."""

import logging
from pathlib import Path

# NOTE: `fitz` is the internal package name for PyMuPDF. PyPI hosts another
# package called `fitz` (https://pypi.org/project/fitz/) that is completely
# unrelated to PDF parsing.
import fitz
from slugify import slugify
from sqlalchemy import select

from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks import app
from ambuda.tasks.utils import CeleryTaskStatus, TaskStatus
from config import create_config_only_app


def _split_pdf_into_pages(
    pdf_path: Path, output_dir: Path, task_status: TaskStatus
) -> int:
    """Split the given PDF into N .jpg images, one image per page.

    :param pdf_path: filesystem path to the PDF we should process.
    :param output_dir: the directory to which we'll write these images.
    :return: the page count, which we use downstream.
    """
    doc = fitz.open(pdf_path)
    task_status.progress(0, doc.page_count)
    for page in doc:
        n = page.number + 1
        pix = page.get_pixmap(dpi=200)
        output_path = output_dir / f"{n}.jpg"
        pix.pil_save(output_path, optimize=True)
        task_status.progress(n, doc.page_count)
    return doc.page_count


def _add_project_to_database(
    display_title: str, slug: str, num_pages: int, creator_id: int
):
    """Create a project on the database.

    :param display_title: the project title
    :param num_pages: the number of pages in the project
    """

    logging.info(f"Creating project (slug = {slug}) ...")
    session = q.get_session()
    board = db.Board(title=f"{slug} discussion board")
    session.add(board)
    session.flush()

    project = db.Project(slug=slug, display_title=display_title, creator_id=creator_id)
    project.board_id = board.id
    session.add(project)
    session.flush()

    logging.info(f"Fetching project and status (slug = {slug}) ...")
    stmt = select(db.PageStatus).filter_by(name="reviewed-0")
    unreviewed = session.scalars(stmt).one()

    logging.info(f"Creating {num_pages} Page entries (slug = {slug}) ...")
    for n in range(1, num_pages + 1):
        session.add(
            db.Page(
                project_id=project.id,
                slug=str(n),
                order=n,
                status_id=unreviewed.id,
            )
        )
    session.commit()


def create_project_inner(
    *,
    display_title: str,
    pdf_path: str,
    output_dir: str,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
):
    """Split the given PDF into pages and register the project on the database.

    We separate this function from `create_project` so that we can run this
    function in a non-Celery context (for example, in `cli.py`).

    :param display_title: the project's title.
    :param pdf_path: local path to the source PDF.
    :param output_dir: local path where page images will be stored.
    :param app_environment: the app environment, e.g. `"development"`.
    :param creator_id: the user that created this project.
    :param task_status: tracks progress on the task.
    """
    logging.info(f'Received upload task "{display_title}" for path {pdf_path}.')

    # Tasks must be idempotent. Exit if the project already exists.
    app = create_config_only_app(app_environment)
    with app.app_context():
        session = q.get_session()
        slug = slugify(display_title)
        stmt = select(db.Project).filter_by(slug=slug)
        project = session.scalars(stmt).first()

    if project:
        raise ValueError(
            f'Project "{display_title}" already exists. Please choose a different title.'
        )

    pdf_path = Path(pdf_path)
    pages_dir = Path(output_dir)

    num_pages = _split_pdf_into_pages(Path(pdf_path), Path(pages_dir), task_status)
    with app.app_context():
        _add_project_to_database(
            display_title=display_title,
            slug=slug,
            num_pages=num_pages,
            creator_id=creator_id,
        )

    task_status.success(num_pages, slug)


@app.task(bind=True)
def create_project(
    self,
    *,
    display_title: str,
    pdf_path: str,
    output_dir: str,
    app_environment: str,
    creator_id: int,
):
    """Split the given PDF into pages and register the project on the database.

    For argument details, see `create_project_inner`.
    """
    task_status = CeleryTaskStatus(self)
    create_project_inner(
        display_title=display_title,
        pdf_path=pdf_path,
        output_dir=output_dir,
        app_environment=app_environment,
        creator_id=creator_id,
        task_status=task_status,
    )
