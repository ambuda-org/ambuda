"""Background tasks for proofing projects."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from ambuda import consts
from ambuda.enums import SitePageStatus
from ambuda.tasks import app
from ambuda.tasks.utils import CeleryTaskStatus, TaskStatus, get_db_session
from ambuda.utils import google_ocr
from ambuda.utils import sarvam_ocr
from ambuda.utils.revisions import add_revision


def _run_ocr_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    """Run OCR for a single page without Flask dependency."""

    with get_db_session(app_env) as (session, query, cfg):
        logging.info(f"Running OCR for page {project_slug}/{page_slug}")
        bot_user = query.user(consts.BOT_USERNAME)
        if bot_user is None:
            raise ValueError(f'User "{consts.BOT_USERNAME}" is not defined.')

        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_ = query.page(project_.id, page_slug)
        if not page_:
            raise ValueError(f"Unknown page {project_slug}/{page_slug}")

        # The actual API call.
        google_ocr_response = google_ocr.run(page_, cfg.S3_BUCKET, cfg.CLOUDFRONT_BASE_URL)
        project = query.project(project_slug)
        page = query.page(project.id, page_slug)

        page.ocr_bounding_boxes = google_ocr.serialize_bounding_boxes(
            google_ocr_response.bounding_boxes
        )
        sarvam_ocr_response = sarvam_ocr.run(page, cfg.S3_BUCKET, cfg.CLOUDFRONT_BASE_URL)

        session.add(page)
        session.commit()

        summary = "Run OCR"
        try:
            _ = add_revision(
                page=page,
                summary=summary,
                content=sarvam_ocr_response.text_content or google_ocr_response.text_content,
                version=0,
                author_id=bot_user.id,
                status=SitePageStatus.R0,
                session=session,
                query=query,
            )
            logging.info(f"Created new revision for page {project_slug}/{page_slug}")
        except Exception as e:
            logging.info(f"OCR failed for page {project_slug}/{page_slug}: {e}")
            raise ValueError(
                f'OCR failed for page "{project.slug}/{page.slug}".'
            ) from e


@app.task(bind=True)
def run_ocr_for_page(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    _run_ocr_for_page_inner(
        app_env,
        project_slug,
        page_slug,
    )


def _replace_ocr_bounding_boxes_for_page_inner(
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    """Re-run OCR for a single page and update only its bounding box data."""

    with get_db_session(app_env) as (session, query, cfg):
        logging.info(
            f"Replacing OCR bounding boxes for page {project_slug}/{page_slug}"
        )

        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_ = query.page(project_.id, page_slug)
        if not page_:
            raise ValueError(f"Unknown page {project_slug}/{page_slug}")

        ocr_response = google_ocr.run(page_, cfg.S3_BUCKET, cfg.CLOUDFRONT_BASE_URL)

        page_.ocr_bounding_boxes = google_ocr.serialize_bounding_boxes(
            ocr_response.bounding_boxes
        )
        session.add(page_)
        session.commit()
        logging.info(f"Updated bounding boxes for page {project_slug}/{page_slug}")


@app.task(bind=True)
def replace_ocr_bounding_boxes_for_page(
    self,
    *,
    app_env: str,
    project_slug: str,
    page_slug: str,
):
    _replace_ocr_bounding_boxes_for_page_inner(
        app_env,
        project_slug,
        page_slug,
    )


def _run_ocr_threaded(
    page_fn,
    app_env: str,
    project_slug: str,
    page_slugs: list[str],
    task_status: TaskStatus,
    max_workers: int = 4,
):
    """Run a per-page OCR function concurrently using threads.

    :param page_fn: callable(app_env, project_slug, page_slug) to run per page.
    :param app_env: the app environment.
    :param project_slug: the project slug.
    :param page_slugs: list of page slugs to process.
    :param task_status: tracks progress on the task.
    :param max_workers: max concurrent threads.
    """
    total = len(page_slugs)
    completed = [0]
    failed_pages = []
    task_status.progress(0, total, failed_pages=[])

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_slug = {}
        for slug in page_slugs:
            fut = executor.submit(page_fn, app_env, project_slug, slug)
            future_to_slug[fut] = slug

        for fut in as_completed(future_to_slug):
            slug = future_to_slug[fut]
            try:
                fut.result()
            except Exception:
                logging.exception(f"OCR failed for page {project_slug}/{slug}")
                failed_pages.append(slug)
            completed[0] += 1
            task_status.progress(completed[0], total, failed_pages=failed_pages)

    task_status.success(total, project_slug, failed_pages=failed_pages)


def run_ocr_for_project_inner(
    *,
    app_env: str,
    project_slug: str,
    task_status: TaskStatus,
):
    """Run OCR on all unedited pages in a project using threads.

    :param app_env: the app environment.
    :param project_slug: the project slug.
    :param task_status: tracks progress on the task.
    """
    with get_db_session(app_env) as (session, query, cfg):
        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_slugs = [p.slug for p in project_.pages if p.version == 0]

    if not page_slugs:
        task_status.success(0, project_slug)
        return

    _run_ocr_threaded(
        _run_ocr_for_page_inner,
        app_env,
        project_slug,
        page_slugs,
        task_status,
    )


@app.task(bind=True)
def run_ocr_for_project(
    self,
    *,
    app_env: str,
    project_slug: str,
):
    """Run OCR on all unedited pages in a project.

    Uses threads within a single Celery task instead of dispatching
    one task per page, reducing worker memory pressure.
    """
    task_status = CeleryTaskStatus(self)
    run_ocr_for_project_inner(
        app_env=app_env,
        project_slug=project_slug,
        task_status=task_status,
    )


def replace_ocr_bounding_boxes_for_project_inner(
    *,
    app_env: str,
    project_slug: str,
    task_status: TaskStatus,
):
    """Replace OCR bounding boxes for all pages in a project using threads.

    :param app_env: the app environment.
    :param project_slug: the project slug.
    :param task_status: tracks progress on the task.
    """
    with get_db_session(app_env) as (session, query, cfg):
        project_ = query.project(project_slug)
        if not project_:
            raise ValueError(f"Unknown project {project_slug}")
        page_slugs = [p.slug for p in project_.pages]

    if not page_slugs:
        task_status.success(0, project_slug)
        return

    _run_ocr_threaded(
        _replace_ocr_bounding_boxes_for_page_inner,
        app_env,
        project_slug,
        page_slugs,
        task_status,
    )


@app.task(bind=True)
def replace_ocr_bounding_boxes_for_project(
    self,
    *,
    app_env: str,
    project_slug: str,
):
    """Replace OCR bounding boxes for all pages in a project.

    Uses threads within a single Celery task instead of dispatching
    one task per page, reducing worker memory pressure.
    """
    task_status = CeleryTaskStatus(self)
    replace_ocr_bounding_boxes_for_project_inner(
        app_env=app_env,
        project_slug=project_slug,
        task_status=task_status,
    )
