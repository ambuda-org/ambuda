"""Background tasks for proofing projects."""

from pathlib import Path

import fitz
from celery import states
from slugify import slugify

from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks import app
from config import create_config_only_app


class TaskStatus:
    """Helper class to track progress on a task.

    - For Celery tasks, use CeleryTaskStatus.
    - For local usage (unit tests, CLI, ...), use a LocalTaskStatus instead.
    """

    def progress(self, current: int, total: int):
        """Update the task's progress.

        :param current: progress numerator
        :param total: progress denominator
        """
        raise NotImplementedError

    def success(self, num_pages: int, slug: str):
        """Mark the task as a success.

        # FIXME(arun): make this API more generic.
        """
        raise NotImplementedError

    def failure(self, message: str):
        """Mark the task as failed."""
        raise NotImplementedError


class CeleryTaskStatus(TaskStatus):
    """Helper class to track progress on a Celery task."""

    def __init__(self, task):
        self.task = task

    def progress(self, current: int, total: int):
        """Update the task's progress.

        :param current: progress numerator
        :param total: progress denominator
        """
        # Celery doesn't have a "PROGRESS" state, so just use a hard-coded string.
        self.task.update_state(
            state="PROGRESS", meta={"current": current, "total": total}
        )

    def success(self, num_pages: int, slug: str):
        """Mark the task as a success."""
        self.task.update_state(
            state=states.SUCCESS,
            meta={"current": num_pages, "total": num_pages, "slug": slug},
        )

    def failure(self, message: str):
        """Mark the task as failed."""
        self.task.update_state(state=states.FAILURE, meta={"message": message})


class LocalTaskStatus(TaskStatus):
    """Helper class to track progress on a task running locally."""

    def progress(self, current: int, total: int):
        print(f"{current} / {total} complete")

    def success(self, num_pages: int, slug: str):
        print(f"Succeeded. Project is at {slug}.")

    def failure(self, message: str):
        print(f"Failed. ({message})")


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


def _add_project_to_database(title: str, slug: str, num_pages: int, creator_id: int):
    """Create a project on the database.

    :param title: the project title
    :param num_pages: the number of pages in the project
    """

    print(f"Creating project (slug = {slug}) ...")
    session = q.get_session()
    board = db.Board(title=f"{slug} discussion board")
    session.add(board)
    session.flush()

    project = db.Project(slug=slug, title=title, creator_id=creator_id)
    project.board_id = board.id
    session.add(project)
    session.flush()

    print(f"Fetching project and status (slug = {slug}) ...")
    unreviewed = session.query(db.PageStatus).filter_by(name="reviewed-0").one()

    print(f"Creating {num_pages} Page entries (slug = {slug}) ...")
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


def _create_project_inner(
    *,
    title: str,
    pdf_path: str,
    output_dir: str,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
):
    """Split the given PDF into pages and register the project on the database.

    We separate this function from `create_project` so that we can run this
    function in a non-Celery context (for example, in `cli.py`).

    :param title: the project title.
    :param pdf_path: local path to the source PDF.
    :param output_dir: local path where page images will be stored.
    :param app_environment: the app environment, e.g. `"development"`.
    :param creator_id: the user that created this project.
    :param task_status: tracks progress on the task.
    """
    print(f'Received upload task "{title}" for path {pdf_path}.')

    # Tasks must be idempotent. Exit if the project already exists.
    app = create_config_only_app(app_environment)
    with app.app_context():
        session = q.get_session()
        slug = slugify(title)
        project = session.query(db.Project).filter_by(slug=slug).first()

    if project:
        raise ValueError(
            f'Project "{title}" already exists. Please choose a different title.'
        )

    pdf_path = Path(pdf_path)
    pages_dir = Path(output_dir)

    num_pages = _split_pdf_into_pages(Path(pdf_path), Path(pages_dir), task_status)
    with app.app_context():
        _add_project_to_database(
            title=title,
            slug=slug,
            num_pages=num_pages,
            creator_id=creator_id,
        )

    task_status.success(num_pages, slug)


@app.task(bind=True)
def create_project(
    self,
    *,
    title: str,
    pdf_path: str,
    output_dir: str,
    app_environment: str,
    creator_id: int,
):
    """Split the given PDF into pages and register the project on the database.

    For argument details, see `_create_project_inner`.
    """
    task_status = CeleryTaskStatus(self)
    _create_project_inner(
        title=title,
        pdf_path=pdf_path,
        output_dir=output_dir,
        app_environment=app_environment,
        creator_id=creator_id,
        task_status=task_status,
    )
