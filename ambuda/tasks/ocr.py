"""Background tasks for proofing projects."""

import time

from celery import group

from ambuda.tasks import app
from ambuda.tasks.utils import TaskStatus, CeleryTaskStatus
from ambuda import queries as q
from config import create_config_only_app


def _run_ocr_for_page_inner(project_slug: str, page_slug: str, user_id: int):
    print(f"{project_slug}, {page_slug}, {user_id}")
    time.sleep(2)
    return "done"


@app.task(bind=True)
def run_ocr_for_page(self, **kw):
    task_status = CeleryTaskStatus(self)
    _run_ocr_for_page_inner(**kw, task_status=task_status)


def _run_ocr_for_book_inner(
    project_slug: str, app_environment: str, user_id: int, task_status: TaskStatus
):
    flask_app = create_config_only_app(app_environment)
    with flask_app.app_context():
        project = q.project(project_slug)
        unedited_pages = [p for p in project.pages if p.version == 0]

    tasks = group(
        run_ocr_for_page(project_slug, p.slug, user_id) for p in unedited_pages
    )


@app.task(bind=True)
def run_ocr_for_book(
    self,
    **kw,
):
    task_status = CeleryTaskStatus(self)
    _run_ocr_for_book_inner(**kw, task_status=task_status)
