"""Background tasks for proofing projects."""

import gc
import logging
import uuid
import os
import json
import re
import hashlib
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import requests

from slugify import slugify
from sqlalchemy import select

from ambuda import database as db
from ambuda.utils.s3 import S3Path
from ambuda.tasks import app
from ambuda.tasks.utils import (
    CeleryTaskStatus,
    LocalTaskStatus,
    TaskStatus,
    get_db_session,
)


def _save_page_image(
    pdf_path: Path, page_index: int, output_path: Path, dpi: int = 200
):
    """Render a single PDF page to a JPG file.

    Opens and closes the PDF document for each page to prevent PyMuPDF from
    accumulating internal caches that cause memory to spike on large PDFs.

    :param pdf_path: filesystem path to the source PDF.
    :param page_index: zero-based page number to render.
    :param output_path: where to write the image.
    :param dpi: resolution for rendering.
    """
    import fitz

    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    pix = page.get_pixmap(dpi=dpi)
    pix.pil_save(str(output_path), optimize=True)
    pix = None
    page = None
    doc.close()
    del doc
    gc.collect()


def _split_pdf_into_pages(
    pdf_path: Path, output_dir: Path, task_status: TaskStatus
) -> list[str]:
    """Split the given PDF into N .jpg images, one image per page.

    :param pdf_path: filesystem path to the PDF we should process.
    :param output_dir: the directory to which we'll write these images.
    :return: a list of UUIDs for each page, in order.
    """
    import fitz

    doc = fitz.open(pdf_path)
    num_pages = doc.page_count
    doc.close()

    task_status.progress(0, num_pages)
    page_uuids = []

    for n in range(num_pages):
        page_uuid = str(uuid.uuid4())
        page_uuids.append(page_uuid)

        output_path = output_dir / f"{page_uuid}.jpg"
        _save_page_image(pdf_path, n, output_path)
        task_status.progress(n + 1, num_pages)

    return page_uuids


RESERVED_SLUGS = {"texts", "dashboard", "recent-changes", "talk", "suggestions"}


def _generate_unique_slug(session, display_title: str) -> str:
    """Generate a unique project slug from a display title.

    If the base slug collides with an existing project or a reserved slug,
    appends an incrementing numeric suffix (e.g. ``my-title-2``).
    """
    base_slug = slugify(display_title)
    slug = base_slug
    suffix = 2
    while True:
        if slug in RESERVED_SLUGS:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
            continue
        existing = session.scalars(select(db.Project).filter_by(slug=slug)).first()
        if not existing:
            break
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    return slug


def _add_project_to_database(
    session,
    display_title: str,
    slug: str,
    page_uuids: list[str],
    creator_id: int,
    source_url: str | None = None,
):
    """Create a project on the database.

    :param session: database session
    :param display_title: the project title
    :param slug: the project slug
    :param page_uuids: list of UUIDs for each page, in order
    :param creator_id: the user ID of the creator
    :param source_url: if provided, creates a ProjectSource with this URL
    """

    logging.info(f"Creating project (slug = {slug}) ...")
    board = db.Board(title=f"{slug} discussion board")
    session.add(board)
    session.flush()

    project = db.Project(
        slug=slug,
        display_title=display_title,
        creator_id=creator_id,
    )
    project.board_id = board.id
    session.add(project)
    session.flush()

    if source_url:
        session.add(
            db.ProjectSource(
                project_id=project.id,
                description=display_title,
                url=source_url,
                author_id=creator_id,
            )
        )

    logging.info(f"Fetching project and status (slug = {slug}) ...")
    stmt = select(db.PageStatus).filter_by(name="reviewed-0")
    unreviewed = session.scalars(stmt).one()

    num_pages = len(page_uuids)
    logging.info(f"Creating {num_pages} Page entries (slug = {slug}) ...")
    for n, page_uuid in enumerate(page_uuids, start=1):
        session.add(
            db.Page(
                project_id=project.id,
                slug=str(n),
                uuid=page_uuid,
                order=n,
                status_id=unreviewed.id,
            )
        )
    session.commit()


def create_project_from_local_pdf_inner(
    *,
    pdf_path: str,
    display_title: str | None = None,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
    source_url: str | None = None,
    engine=None,
):
    """Split a local PDF into pages and register the project on the database.

    We separate this function from `create_project_from_local_pdf` so that we can run this
    function in a non-Celery context (for example, in `cli.py`).

    :param pdf_path: local path to the source PDF.
    :param display_title: optional custom display title for the project.
    :param app_environment: the app environment, e.g. `"development"`.
    :param creator_id: the user that created this project.
    :param task_status: tracks progress on the task.
    :param engine: optional SQLAlchemy engine. Tests should pass this to share
                   the same :memory: database.
    """

    if not display_title:
        with open(pdf_path, "rb") as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()
        timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        hash_prefix = file_hash[:12]
        display_title = f"Project {hash_prefix} ({timestamp})"

    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        slug = _generate_unique_slug(session, display_title)

        upload_folder = getattr(config_obj, "UPLOAD_FOLDER", None)
        if upload_folder:
            pages_dir = Path(upload_folder) / "pages"
            pages_dir.mkdir(parents=True, exist_ok=True)
        else:
            pages_dir = Path(tempfile.mkdtemp(prefix=f"ambuda_pages_{slug}_"))

        page_uuids = _split_pdf_into_pages(Path(pdf_path), pages_dir, task_status)

        _add_project_to_database(
            session=session,
            display_title=display_title,
            slug=slug,
            page_uuids=page_uuids,
            creator_id=creator_id,
            source_url=source_url,
        )

        # Move assets to s3.
        stmt = select(db.Project).filter_by(slug=slug)
        project = session.scalars(stmt).first()
        if not project:
            raise ValueError(f"Could not create project {display_title}")

        s3_bucket = config_obj.S3_BUCKET
        if s3_bucket:
            s3_dest = project.s3_path(s3_bucket)
            if s3_dest.exists():
                logging.info(f"S3 path {s3_dest} already exists.")
            else:
                s3_dest.upload_file(pdf_path)
                logging.info(f"Uploaded {project.id} PDF path to {s3_dest}.")

            Path(pdf_path).unlink()
            logging.info(f"Removed local file {pdf_path}.")

            pages_dir = Path(pages_dir)
            logging.info(f"Uploading {len(page_uuids)} page images to S3...")

            stmt = select(db.Page).filter_by(project_id=project.id)
            pages = session.scalars(stmt).all()
            page_map = {page.uuid: page for page in pages}

            for page_uuid in page_uuids:
                local_page_path = pages_dir / f"{page_uuid}.jpg"
                if not local_page_path.exists():
                    logging.warning(f"Page image not found: {local_page_path}")
                    continue

                page = page_map.get(page_uuid)
                if not page:
                    logging.warning(f"Page with UUID {page_uuid} not found in database")
                    continue

                s3_page_path = page.s3_path(s3_bucket)
                if s3_page_path.exists():
                    logging.info(f"Page {page_uuid} already exists in S3, skipping.")
                else:
                    s3_page_path.upload_file(str(local_page_path))
                    logging.info(f"Uploaded page {page_uuid} to {s3_page_path}.")

                local_page_path.unlink()

            logging.info(f"Finished uploading page images to S3.")
        else:
            logging.info(f"No s3 bucket found")

    return task_status.success(len(page_uuids), slug)


@app.task(bind=True)
def create_project_from_local_pdf(
    self,
    *,
    pdf_path: str,
    display_title: str | None = None,
    creator_id: int,
    app_environment: str,
    source_url: str | None = None,
):
    """Split a local PDF into pages and register the project on the database.

    For argument details, see `create_project_from_local_pdf_inner`.
    """
    task_status = CeleryTaskStatus(self)
    return create_project_from_local_pdf_inner(
        pdf_path=pdf_path,
        display_title=display_title,
        creator_id=creator_id,
        task_status=task_status,
        app_environment=app_environment,
        source_url=source_url,
    )


def create_project_from_url_inner(
    *,
    pdf_url: str,
    display_title: str | None = None,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
    engine=None,
):
    """Download a PDF from URL and create a project.

    :param pdf_url: URL to download PDF from.
    :param display_title: optional custom display title for the project.
    :param app_environment: the app environment, e.g. `"development"`.
    :param creator_id: the user that created this project.
    :param task_status: tracks progress on the task.
    :param engine: optional SQLAlchemy engine. Tests should pass this to share
                   the same :memory: database.
    """

    temp_dir = Path(tempfile.gettempdir())
    temp_pdf_path = temp_dir / f"ambuda_pdf_{uuid.uuid4()}.pdf"
    try:
        logging.info(f"Downloading PDF from {pdf_url}...")
        with requests.get(pdf_url, stream=True) as response:
            response.raise_for_status()
            with open(temp_pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()
        raise ValueError(f"Failed to download PDF from {pdf_url}: {e}") from e

    try:
        return create_project_from_local_pdf_inner(
            pdf_path=str(temp_pdf_path),
            display_title=display_title,
            app_environment=app_environment,
            creator_id=creator_id,
            task_status=task_status,
            source_url=pdf_url,
            engine=engine,
        )
    except Exception:
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()
        raise


@app.task(bind=True)
def create_project_from_url(
    self,
    *,
    pdf_url: str,
    display_title: str | None = None,
    creator_id: int,
    app_environment: str,
):
    """Download a PDF from URL and create a project.

    For argument details, see `create_project_from_url_inner`.
    """
    task_status = CeleryTaskStatus(self)
    return create_project_from_url_inner(
        pdf_url=pdf_url,
        display_title=display_title,
        creator_id=creator_id,
        task_status=task_status,
        app_environment=app_environment,
    )


def create_projects_from_urls_inner(
    *,
    pdf_urls: list[str],
    display_titles: list[str] | None = None,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
    engine=None,
):
    """Create multiple projects from a list of PDF URLs.

    Processes each URL serially: download one, process, cleanup, then next.
    Continues processing remaining URLs if one fails.

    :param pdf_urls: list of URLs pointing to PDF files.
    :param display_titles: list of titles for each URL, same length as pdf_urls.
    :param app_environment: the app environment, e.g. ``"development"``.
    :param creator_id: the user that created these projects.
    :param task_status: tracks progress on the task.
    :param engine: optional SQLAlchemy engine for tests.
    """
    total = len(pdf_urls)
    completed_projects = []
    task_status.progress(
        0, total, multi_upload=True, completed_projects=completed_projects
    )

    for i, pdf_url in enumerate(pdf_urls):
        if display_titles and i < len(display_titles):
            display_title = display_titles[i]
        else:
            url_path = pdf_url.rstrip("/").split("?")[0]
            filename = url_path.split("/")[-1]
            display_title = Path(filename).stem if filename else f"project-{i + 1}"

        logging.info(
            f"Processing URL {i + 1}/{total}: {pdf_url} (title: {display_title})"
        )

        try:
            # Use LocalTaskStatus for inner calls so they don't overwrite
            # the outer Celery task's state (e.g. setting SUCCESS prematurely
            # after the first PDF).
            create_project_from_url_inner(
                pdf_url=pdf_url,
                display_title=display_title,
                app_environment=app_environment,
                creator_id=creator_id,
                task_status=LocalTaskStatus(),
                engine=engine,
            )
            slug = slugify(display_title)
            completed_projects.append(
                {
                    "title": display_title,
                    "slug": slug,
                    "status": "success",
                    "error": None,
                }
            )
            logging.info(f"Successfully created project: {display_title}")
        except Exception as e:
            error_detail = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            logging.error(
                f"Failed to create project from {pdf_url}: {error_detail}",
                exc_info=True,
            )
            completed_projects.append(
                {
                    "title": display_title,
                    "slug": None,
                    "status": "failed",
                    "error": error_detail,
                }
            )

        task_status.progress(
            i + 1,
            total,
            multi_upload=True,
            completed_projects=completed_projects,
            current_url=pdf_url,
        )

    success_msg = f"Created {len([p for p in completed_projects if p['status'] == 'success'])} projects from {total} URLs"
    logging.info(success_msg)
    return task_status.success(
        len([p for p in completed_projects if p["status"] == "success"]),
        slug=None,
        multi_upload=True,
        completed_projects=completed_projects,
    )


@app.task(bind=True, time_limit=7200)
def create_projects_from_urls(
    self,
    *,
    pdf_urls: list[str],
    display_titles: list[str] | None = None,
    creator_id: int,
    app_environment: str,
):
    """Create multiple projects from a list of PDF URLs.

    For argument details, see `create_projects_from_urls_inner`.
    """
    task_status = CeleryTaskStatus(self)
    return create_projects_from_urls_inner(
        pdf_urls=pdf_urls,
        display_titles=display_titles,
        app_environment=app_environment,
        creator_id=creator_id,
        task_status=task_status,
    )


def _extract_gdrive_folder_id(folder_url: str) -> str:
    """Extract the folder ID from a Google Drive folder URL.

    Supports formats like:
    - https://drive.google.com/drive/folders/FOLDER_ID
    - https://drive.google.com/drive/folders/FOLDER_ID?usp=sharing
    """
    # Try to extract folder ID using regex
    match = re.search(r"/folders/([a-zA-Z0-9_-]+)", folder_url)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract folder ID from URL: {folder_url}")


def _list_gdrive_folder_pdfs(folder_id: str, api_key: str = None):
    """List all PDF files in a public Google Drive folder.

    :param folder_id: The Google Drive folder ID
    :param api_key: Optional Google Drive API key
    :return: List of dicts with 'id' and 'name' keys
    """
    if api_key:
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": f"'{folder_id}' in parents and mimeType='application/pdf'",
            "key": api_key,
            "fields": "files(id,name)",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("files", [])
        except Exception as e:
            logging.error(f"Failed to list files using API: {e}")
            raise ValueError(
                f"Failed to access Google Drive folder. Make sure it's publicly accessible. Error: {e}"
            )
    else:
        raise ValueError(
            "Google Drive API key not configured. Please set GOOGLE_DRIVE_API_KEY in your configuration."
        )


def _get_gdrive_file_download_url(file_id: str) -> str:
    """Get the download URL for a Google Drive file.

    :param file_id: The Google Drive file ID
    :return: Direct download URL
    """
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def create_projects_from_gdrive_folder_inner(
    *,
    folder_url: str,
    upload_folder: str,
    app_environment: str,
    creator_id: int,
    task_status: TaskStatus,
    engine=None,
):
    """Create multiple projects from PDFs in a Google Drive folder.

    :param folder_url: Google Drive folder URL
    :param upload_folder: Base upload folder
    :param app_environment: The app environment
    :param creator_id: The user that created these projects
    :param task_status: Tracks progress on the task
    :param engine: Optional SQLAlchemy engine
    """
    logging.info(f"Processing Google Drive folder: {folder_url}")

    # Extract folder ID
    try:
        folder_id = _extract_gdrive_folder_id(folder_url)
        logging.info(f"Extracted folder ID: {folder_id}")
    except ValueError as e:
        raise ValueError(f"Invalid Google Drive folder URL: {e}")

    # Get API key from config
    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        api_key = getattr(config_obj, "GOOGLE_DRIVE_API_KEY", None)

        # List all PDFs in the folder
        try:
            pdf_files = _list_gdrive_folder_pdfs(folder_id, api_key)
            logging.info(f"Found {len(pdf_files)} PDF files in folder")
        except ValueError as e:
            raise

        if not pdf_files:
            raise ValueError("No PDF files found in the Google Drive folder.")

        # Update progress
        task_status.progress(0, len(pdf_files))

        # Create a project for each PDF
        created_projects = []
        for idx, pdf_file in enumerate(pdf_files):
            file_id = pdf_file["id"]
            file_name = pdf_file["name"]

            # Use filename (without extension) as the title
            title = Path(file_name).stem
            logging.info(f"Creating project for: {title} ({file_name})")

            # Get download URL
            download_url = _get_gdrive_file_download_url(file_id)

            # Create project using the existing logic
            try:
                create_project_from_url_inner(
                    pdf_url=download_url,
                    display_title=title,
                    app_environment=app_environment,
                    creator_id=creator_id,
                    task_status=LocalTaskStatus(),
                    engine=engine,
                )
                created_projects.append(title)
                logging.info(f"Successfully created project: {title}")
            except Exception as e:
                logging.error(f"Failed to create project for {title}: {e}")
                # Continue with other files even if one fails

            # Update progress
            task_status.progress(idx + 1, len(pdf_files))

        # Return summary
        success_msg = (
            f"Created {len(created_projects)} projects from {len(pdf_files)} PDFs"
        )
        logging.info(success_msg)
        return task_status.success(len(created_projects), success_msg)


@app.task(bind=True)
def create_projects_from_gdrive_folder(
    self,
    *,
    folder_url: str,
    upload_folder: str,
    app_environment: str,
    creator_id: int,
):
    """Create multiple projects from PDFs in a Google Drive folder.

    For argument details, see `create_projects_from_gdrive_folder_inner`.
    """
    task_status = CeleryTaskStatus(self)
    return create_projects_from_gdrive_folder_inner(
        folder_url=folder_url,
        upload_folder=upload_folder,
        app_environment=app_environment,
        creator_id=creator_id,
        task_status=task_status,
    )


def delete_project_inner(
    *,
    project_slug: str,
    app_environment: str,
    engine=None,
):
    """Delete a project and all its associated S3 assets.

    Removes page images from S3, then the source PDF, then the project
    record itself (which cascade-deletes pages, revisions, and the board).

    :param project_slug: slug identifying the project to delete.
    :param app_environment: the app environment, e.g. ``"development"``.
    :param engine: optional SQLAlchemy engine for tests.
    """
    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        stmt = select(db.Project).filter_by(slug=project_slug)
        project = session.scalars(stmt).first()
        if not project:
            raise ValueError(f'Project "{project_slug}" not found.')

        s3_bucket = config_obj.S3_BUCKET

        if s3_bucket:
            # 1. Delete all page images from S3.
            pages_stmt = select(db.Page).filter_by(project_id=project.id)
            pages = session.scalars(pages_stmt).all()

            for page in pages:
                try:
                    page.s3_path(s3_bucket).delete()
                    logging.info(f"Deleted page image {page.uuid} from S3.")
                except Exception as e:
                    logging.warning(
                        f"Could not delete page image {page.uuid} from S3: {e}"
                    )

            # 2. Delete the source PDF from S3.
            try:
                project.s3_path(s3_bucket).delete()
                logging.info(f"Deleted project PDF for {project_slug} from S3.")
            except Exception as e:
                logging.warning(
                    f"Could not delete project PDF for {project_slug} from S3: {e}"
                )

        # 3. Delete the project (cascades to pages, revisions, board).
        try:
            session.delete(project)
            session.commit()
            logging.info(f"Deleted project {project_slug} from database.")
        except Exception as e:
            session.rollback()
            logging.error(f"Error deleting project {project_slug} from database: {e}")
            raise


@app.task(bind=True)
def delete_project(
    self,
    *,
    project_slug: str,
    app_environment: str,
):
    """Delete a project and all its associated S3 assets.

    For argument details, see `delete_project_inner`.
    """
    delete_project_inner(
        project_slug=project_slug,
        app_environment=app_environment,
    )


def regenerate_project_pages_inner(
    *,
    project_slug: str,
    app_environment: str,
    task_status: TaskStatus,
    engine=None,
):
    """Re-render page images for an existing project from its source PDF.

    Downloads the project's PDF, re-renders each page as a JPG using the
    existing page UUIDs, and uploads the new images to replace the old ones.

    :param project_slug: slug identifying the project.
    :param app_environment: the app environment, e.g. ``"development"``.
    :param task_status: tracks progress on the task.
    :param engine: optional SQLAlchemy engine for tests.
    """
    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        stmt = select(db.Project).filter_by(slug=project_slug)
        project = session.scalars(stmt).first()
        if not project:
            raise ValueError(f'Project "{project_slug}" not found.')

        pages_stmt = (
            select(db.Page).filter_by(project_id=project.id).order_by(db.Page.order)
        )
        pages = session.scalars(pages_stmt).all()
        if not pages:
            raise ValueError(f'Project "{project_slug}" has no pages.')

        s3_bucket = config_obj.S3_BUCKET

        temp_dir = Path(tempfile.mkdtemp(prefix=f"ambuda_regen_{project_slug}_"))
        pdf_path = temp_dir / "source.pdf"

        try:
            if not s3_bucket:
                raise ValueError("No S3 bucket configured.")

            s3_pdf_path = project.s3_path(s3_bucket)
            if not s3_pdf_path.exists():
                raise ValueError(
                    f'Source PDF not found in S3 for project "{project_slug}".'
                )
            s3_pdf_path.download_file(str(pdf_path))

            import fitz

            doc = fitz.open(pdf_path)
            num_pages = doc.page_count
            doc.close()

            if num_pages != len(pages):
                logging.warning(
                    f"PDF has {num_pages} pages but project has {len(pages)} "
                    f"pages in the database; rendering min({num_pages}, {len(pages)})."
                )
                raise ValueError(
                    f"PDF length and project length don't match ({num_pages} != {len(pages)})"
                )

            task_status.progress(0, num_pages, upload_current=0, upload_total=num_pages)

            upload_count = [0]
            upload_lock = threading.Lock()

            def _upload_and_cleanup(s3_path, local_path):
                s3_path.upload_file(str(local_path))
                local_path.unlink()
                with upload_lock:
                    upload_count[0] += 1

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for i in range(num_pages):
                    page_obj = pages[i]
                    image_path = temp_dir / f"{page_obj.uuid}.jpg"
                    _save_page_image(pdf_path, i, image_path)
                    fut = executor.submit(
                        _upload_and_cleanup,
                        page_obj.s3_path(s3_bucket),
                        image_path,
                    )
                    futures.append(fut)
                    with upload_lock:
                        uc = upload_count[0]
                    task_status.progress(
                        i + 1, num_pages, upload_current=uc, upload_total=num_pages
                    )
                for fut in as_completed(futures):
                    fut.result()
                    with upload_lock:
                        uc = upload_count[0]
                    task_status.progress(
                        num_pages, num_pages, upload_current=uc, upload_total=num_pages
                    )

            logging.info(
                f"Regenerated {num_pages} page images for project {project_slug}."
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return task_status.success(len(pages), project_slug)


@app.task(bind=True)
def regenerate_project_pages(
    self,
    *,
    project_slug: str,
    app_environment: str,
):
    """Re-render page images for an existing project from its source PDF.

    For argument details, see `regenerate_project_pages_inner`.
    """
    task_status = CeleryTaskStatus(self)
    return regenerate_project_pages_inner(
        project_slug=project_slug,
        app_environment=app_environment,
        task_status=task_status,
    )


def replace_project_pdf_inner(
    *,
    project_slug: str,
    pdf_path: str,
    app_environment: str,
    task_status: TaskStatus,
    engine=None,
):
    """Replace the source PDF of an existing project.

    :param project_slug: slug identifying the project.
    :param pdf_path: local path to the replacement PDF.
    :param app_environment: the app environment, e.g. ``"development"``.
    :param task_status: tracks progress on the task.
    :param engine: optional SQLAlchemy engine for tests.
    """
    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        stmt = select(db.Project).filter_by(slug=project_slug)
        project = session.scalars(stmt).first()
        if not project:
            raise ValueError(f'Project "{project_slug}" not found.')

        pages_stmt = (
            select(db.Page).filter_by(project_id=project.id).order_by(db.Page.order)
        )
        existing_pages = list(session.scalars(pages_stmt).all())

        import fitz

        doc = fitz.open(pdf_path)
        new_count = doc.page_count
        doc.close()

        existing_count = len(existing_pages)
        # +1 for the final PDF upload to S3
        total_work = new_count + 1
        upload_total = new_count + 1
        task_status.progress(0, total_work, upload_current=0, upload_total=upload_total)

        s3_bucket = config_obj.S3_BUCKET
        temp_dir = Path(tempfile.mkdtemp(prefix=f"ambuda_replace_{project_slug}_"))

        upload_count = [0]
        upload_lock = threading.Lock()

        def _upload_and_cleanup(s3_path, local_path):
            s3_path.upload_file(str(local_path))
            local_path.unlink()
            with upload_lock:
                upload_count[0] += 1

        def _upload_only(s3_path, local_path):
            s3_path.upload_file(str(local_path))
            with upload_lock:
                upload_count[0] += 1

        try:
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []

                for i in range(min(new_count, existing_count)):
                    page_obj = existing_pages[i]
                    image_path = temp_dir / f"{page_obj.uuid}.jpg"
                    _save_page_image(Path(pdf_path), i, image_path)
                    if s3_bucket:
                        fut = executor.submit(
                            _upload_and_cleanup,
                            page_obj.s3_path(s3_bucket),
                            image_path,
                        )
                        futures.append(fut)
                    else:
                        image_path.unlink()
                    with upload_lock:
                        uc = upload_count[0]
                    task_status.progress(
                        i + 1,
                        total_work,
                        upload_current=uc,
                        upload_total=upload_total,
                    )

                if new_count > existing_count:
                    if existing_pages:
                        max_slug = max(
                            int(p.slug) for p in existing_pages if p.slug.isdigit()
                        )
                        max_order = max(p.order for p in existing_pages)
                    else:
                        max_slug = 0
                        max_order = 0

                    unreviewed = session.scalars(
                        select(db.PageStatus).filter_by(name="reviewed-0")
                    ).one()

                    for i in range(existing_count, new_count):
                        offset = i - existing_count + 1
                        page_uuid = str(uuid.uuid4())
                        new_page = db.Page(
                            project_id=project.id,
                            slug=str(max_slug + offset),
                            uuid=page_uuid,
                            order=max_order + offset,
                            status_id=unreviewed.id,
                        )
                        session.add(new_page)
                        session.flush()

                        image_path = temp_dir / f"{page_uuid}.jpg"
                        _save_page_image(Path(pdf_path), i, image_path)
                        if s3_bucket:
                            fut = executor.submit(
                                _upload_and_cleanup,
                                new_page.s3_path(s3_bucket),
                                image_path,
                            )
                            futures.append(fut)
                        else:
                            image_path.unlink()
                        with upload_lock:
                            uc = upload_count[0]
                        task_status.progress(
                            i + 1,
                            total_work,
                            upload_current=uc,
                            upload_total=upload_total,
                        )

                # Upload the source PDF itself
                if s3_bucket:
                    fut = executor.submit(
                        _upload_only,
                        project.s3_path(s3_bucket),
                        pdf_path,
                    )
                    futures.append(fut)

                task_status.progress(
                    new_count,
                    total_work,
                    upload_current=upload_count[0],
                    upload_total=upload_total,
                )

                # Wait for remaining uploads, reporting progress as each completes
                for fut in as_completed(futures):
                    fut.result()
                    with upload_lock:
                        uc = upload_count[0]
                    task_status.progress(
                        total_work,
                        total_work,
                        upload_current=uc,
                        upload_total=upload_total,
                    )

            session.commit()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    return task_status.success(new_count, project_slug)


@app.task(bind=True, time_limit=1200)
def replace_project_pdf(self, *, project_slug, pdf_path, app_environment):
    """Celery wrapper for `replace_project_pdf_inner`."""
    task_status = CeleryTaskStatus(self)
    return replace_project_pdf_inner(
        project_slug=project_slug,
        pdf_path=pdf_path,
        app_environment=app_environment,
        task_status=task_status,
    )


def replace_project_pdf_from_url_inner(
    *, project_slug, pdf_url, app_environment, task_status, engine=None
):
    """Download a PDF from URL then delegate to `replace_project_pdf_inner`."""
    temp_pdf_path = Path(tempfile.gettempdir()) / f"ambuda_replace_{uuid.uuid4()}.pdf"
    try:
        with requests.get(pdf_url, stream=True) as response:
            response.raise_for_status()
            with open(temp_pdf_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

        result = replace_project_pdf_inner(
            project_slug=project_slug,
            pdf_path=str(temp_pdf_path),
            app_environment=app_environment,
            task_status=task_status,
            engine=engine,
        )
    finally:
        if temp_pdf_path.exists():
            temp_pdf_path.unlink()
    return result


@app.task(bind=True, time_limit=1200)
def replace_project_pdf_from_url(self, *, project_slug, pdf_url, app_environment):
    """Celery wrapper for `replace_project_pdf_from_url_inner`."""
    task_status = CeleryTaskStatus(self)
    return replace_project_pdf_from_url_inner(
        project_slug=project_slug,
        pdf_url=pdf_url,
        app_environment=app_environment,
        task_status=task_status,
    )
