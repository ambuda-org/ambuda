"""Background tasks for proofing projects."""

import time

from celery import group

from ambuda import consts
from ambuda import database as db
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
    username: str,
    task_status: TaskStatus,
):
    """Must run in the application context."""
    time.sleep(2)
    flask_app = create_config_only_app(app_env)

    summary = f"Run OCR"
    content = f"OCR response for {project_slug}/{page_slug}"
    with flask_app.app_context():
        session = q.get_session()
        project = q.project(project_slug)
        page = q.page(project.id, page_slug)
        bot_user = q.user(consts.BOT_USERNAME)

        try:
            add_revision(
                page=page,
                summary=summary,
                content=content,
                status=SitePageStatus.R0,
                version=0,
                author_id=bot_user.id,
            )
        except Exception:
            raise ValueError("Could not create revision")


@app.task(bind=True)
def run_ocr_for_page(
    self, *, app_env: str, project_slug: str, page_slug: str, username: str
):
    task_status = CeleryTaskStatus(self)
    _run_ocr_for_page_inner(
        app_env, project_slug, page_slug, username, task_status=task_status
    )


@app.task(bind=True)
def run_ocr_for_book(self, *, app_env: str, project_slug: str, user_id: int):
    flask_app = create_config_only_app(app_env)
    with flask_app.app_context():
        session = q.get_session()
        project = q.project(project_slug)
        unedited_pages = [p for p in project.pages if p.version == 0]

        user = session.query(db.User).filter_by(id=user_id).first()
        if not user:
            raise ValueError("The requesting user does not exist.")

    tasks = group(
        run_ocr_for_page.s(
            app_env=app_env,
            project_slug=project_slug,
            page_slug=p.slug,
            username=user.username,
        )
        for p in unedited_pages
    )
    tasks.apply_async()
