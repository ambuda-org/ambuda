"""Background tasks for proofing projects."""

import time

from celery import group

from ambuda.enums import SitePageStatus
from ambuda.tasks import app
from ambuda.tasks.utils import TaskStatus, CeleryTaskStatus
from ambuda.utils.revisions import add_revision
from ambuda import queries as q
from config import create_config_only_app


def _run_ocr_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
    user_id: int,
    task_status: TaskStatus,
):
    """Must run in the application context."""
    time.sleep(2)
    flask_app = create_config_only_app(app_env)

    content = f"OCR response for {project_slug}/{page_slug}"
    with flask_app.app_context():
        session = q.get_session()
        project = q.project(project_slug)
        page = q.page(project.id, page_slug)

        try:
            add_revision(
                page=page,
                summary="Run batch OCR",
                content=content,
                status=SitePageStatus.R0,
                version=0,
                author_id=user_id,
            )
        except Exception:
            raise ValueError("Could not create revision")


@app.task(bind=True)
def run_ocr_for_page(
    self, *, app_env: str, project_slug: str, page_slug: str, user_id: int
):
    task_status = CeleryTaskStatus(self)
    _run_ocr_for_page_inner(
        app_env, project_slug, page_slug, user_id, task_status=task_status
    )


@app.task(bind=True)
def run_ocr_for_book(self, *, app_env: str, project_slug: str, user_id: int):
    flask_app = create_config_only_app(app_env)
    with flask_app.app_context():
        project = q.project(project_slug)
        unedited_pages = [p for p in project.pages if p.version == 0]

    tasks = group(
        run_ocr_for_page.s(
            app_env=app_env,
            project_slug=project_slug,
            page_slug=p.slug,
            user_id=user_id,
        )
        for p in unedited_pages
    )
    tasks.apply_async()
