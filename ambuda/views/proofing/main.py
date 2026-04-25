"""Views for basic site pages."""

from collections import defaultdict
from datetime import datetime, timedelta, UTC
import uuid
from pathlib import Path

from xml.etree import ElementTree as ET

from math import ceil

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from flask_wtf import FlaskForm
from slugify import slugify
from sqlalchemy import asc, desc, func, orm, select
from wtforms import FileField, RadioField, SelectField, StringField
from wtforms.validators import DataRequired, Optional, ValidationError
from wtforms.widgets import TextArea

from ambuda import consts
from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.tasks import projects as project_tasks
from ambuda.utils.slug import normalize_for_search
from ambuda.utils.text_validation import try_parse_text_report
from ambuda.views.proofing.decorators import moderator_required, p2_required

bp = Blueprint("proofing", __name__)


def _is_allowed_document_file(filename: str) -> bool:
    """True iff we accept this type of document upload."""
    return Path(filename).suffix == ".pdf"


def _required_if_url(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "url" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_multi_url(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "multi_url" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_gdrive(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "gdrive" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_local(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "local" and not field.data:
            raise ValidationError(message)

    return fn


class CreateTextForm(FlaskForm):
    project_id = SelectField("Project", coerce=int, validators=[DataRequired()])
    title = StringField("Title", validators=[DataRequired()])
    slug = StringField("Slug", validators=[DataRequired()])
    author = StringField("Author", validators=[Optional()])
    language = SelectField("Language", default="sa")
    parent_slug = StringField("Parent slug", validators=[Optional()])
    target = StringField("Filter", validators=[DataRequired()])


class CreateProjectForm(FlaskForm):
    pdf_source = RadioField(
        "Source",
        choices=[
            ("url", "Upload from a URL"),
            ("local", "Upload from my computer"),
            ("multi_url", "Upload from multiple URLs"),
            # TODO: support this later, maybe too powerful for the average user.
            # ("gdrive", "Upload from a Google Drive folder"),
        ],
        validators=[DataRequired()],
    )
    pdf_url = StringField(
        "PDF URL",
        validators=[_required_if_url("Please provide a valid PDF URL.")],
    )
    pdf_urls = StringField(
        "PDF URLs (one per line)",
        widget=TextArea(),
        validators=[
            _required_if_multi_url("Please provide at least one PDF URL."),
        ],
    )
    # gdrive_folder_url = StringField(
    # "Google Drive folder URL",
    # validators=[
    # _required_if_gdrive("Please provide a valid Google Drive folder URL.")
    # ],
    # )
    local_file = FileField(
        "PDF file", validators=[_required_if_local("Please provide a PDF file.")]
    )
    display_title = StringField(
        "Display title",
        validators=[
            _required_if_url("Please provide a title for the project."),
            _required_if_local("Please provide a title for the project."),
        ],
    )


@bp.route("/dashboard")
def dashboard():
    """Show proofing dashboard with overview statistics."""
    from ambuda.models.proofing import ProjectStatus

    session = q.get_session()

    num_active_projects = session.scalar(
        select(func.count(db.Project.id)).filter(
            db.Project.status == ProjectStatus.ACTIVE
        )
    )
    num_pending_projects = session.scalar(
        select(func.count(db.Project.id)).filter(
            db.Project.status == ProjectStatus.PENDING
        )
    )
    num_texts = session.scalar(select(func.count(db.Text.id)))

    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
    num_texts_published_30d = session.scalar(
        select(func.count(db.Text.id)).filter(db.Text.published_at >= thirty_days_ago)
    )
    num_texts_created_30d = session.scalar(
        select(func.count(db.Text.id)).filter(db.Text.created_at >= thirty_days_ago)
    )

    my_projects = []
    if current_user.is_authenticated:
        my_projects = q.user_recent_projects(current_user.id)

    return render_template(
        "proofing/dashboard.html",
        num_active_projects=num_active_projects,
        num_pending_projects=num_pending_projects,
        num_texts=num_texts,
        num_texts_published_30d=num_texts_published_30d,
        num_texts_created_30d=num_texts_created_30d,
        my_projects=my_projects,
    )


@bp.route("/")
def index():
    """List all available proofing projects."""
    from ambuda.models.proofing import ProjectStatus

    session = q.get_session()
    status_classes = {
        SitePageStatus.R2: "bg-green-200",
        SitePageStatus.R1: "bg-yellow-200",
        SitePageStatus.R0: "bg-red-300",
        SitePageStatus.SKIP: "bg-slate-100",
    }

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 25
    search = request.args.get("q", "", type=str).strip()
    sort_field = request.args.get("sort", "title", type=str)
    sort_dir = request.args.get("sort_dir", "asc", type=str)
    genre_ids = request.args.getlist("genre", type=int)
    tag_id = request.args.get("tag", None, type=int)

    is_p2 = current_user.is_authenticated and current_user.is_p2
    valid_statuses = {
        "active",
        "pending",
        "closed-copy",
        "closed-duplicate",
        "closed-quality",
    }
    status_filters = (
        [s for s in request.args.getlist("status") if s in valid_statuses]
        if is_p2
        else []
    )
    if sort_field not in ("title", "created"):
        sort_field = "title"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    projects, total = q.paginated_projects(
        statuses=status_filters or None,
        page=page,
        per_page=per_page,
        sort_field=sort_field,
        sort_dir=sort_dir,
        search=search,
        genre_ids=genre_ids or None,
        tag_id=tag_id,
    )
    total_pages = ceil(total / per_page) if total > 0 else 1

    active_project_ids = [p.id for p in projects]
    statuses_per_project = {}
    progress_per_project = {}
    pages_per_project = {}

    if active_project_ids:
        stmt = (
            select(
                db.Page.project_id,
                db.PageStatus.name,
                func.count(db.Page.id).label("count"),
            )
            .join(db.PageStatus)
            .filter(db.Page.project_id.in_(active_project_ids))
            .group_by(db.Page.project_id, db.PageStatus.name)
        )
        stats = session.execute(stmt).all()

        status_counts_by_project = defaultdict(lambda: defaultdict(int))
        for project_id, status_name, count in stats:
            status_counts_by_project[project_id][status_name] = count

        for proj in projects:
            counts = status_counts_by_project[proj.id]
            num_pages = sum(counts.values())

            if num_pages == 0:
                statuses_per_project[proj.id] = {}
                pages_per_project[proj.id] = 0
                continue

            project_counts = {}
            for enum_value, class_ in status_classes.items():
                count = counts.get(enum_value.value, 0)
                fraction = count / num_pages
                project_counts[class_] = fraction
                if enum_value == SitePageStatus.R0:
                    progress_per_project[proj.id] = 1 - fraction

            statuses_per_project[proj.id] = project_counts
            pages_per_project[proj.id] = num_pages

    genres = q.genres()
    tags = q.project_tags()

    # Count projects per tag for the tag cloud.
    from ambuda.models.proofing import ProjectStatus, project_tag_association

    tag_count_stmt = select(
        project_tag_association.c.tag_id,
        func.count().label("cnt"),
    ).group_by(project_tag_association.c.tag_id)
    tag_counts = {row[0]: row[1] for row in session.execute(tag_count_stmt).all()}

    # Facet counts for sidebar checkboxes.
    status_count_stmt = select(db.Project.status, func.count()).group_by(
        db.Project.status
    )
    status_count_map = {
        {
            ProjectStatus.ACTIVE: "active",
            ProjectStatus.PENDING: "pending",
            ProjectStatus.CLOSED_COPYRIGHT: "closed-copy",
            ProjectStatus.CLOSED_DUPLICATE: "closed-duplicate",
            ProjectStatus.CLOSED_QUALITY: "closed-quality",
        }.get(row[0], ""): row[1]
        for row in session.execute(status_count_stmt).all()
    }

    genre_count_stmt = (
        select(db.Project.genre_id, func.count())
        .filter(db.Project.genre_id.isnot(None))
        .group_by(db.Project.genre_id)
    )
    genre_count_map = {
        row[0]: row[1] for row in session.execute(genre_count_stmt).all()
    }

    template_vars = dict(
        projects=projects,
        statuses_per_project=statuses_per_project,
        progress_per_project=progress_per_project,
        pages_per_project=pages_per_project,
        genres=genres,
        tags=tags,
        tag_counts=tag_counts,
        status_count_map=status_count_map,
        genre_count_map=genre_count_map,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        sort_field=sort_field,
        sort_dir=sort_dir,
        genre_ids=genre_ids,
        tag_id=tag_id,
        status_filters=status_filters,
    )

    if request.args.get("partial"):
        html = render_template("proofing/index_projects.html", **template_vars)
        return jsonify(html=html, total=total)

    return render_template("proofing/index.html", **template_vars)


@bp.route("/help/complete-guide")
def complete_guide():
    """[deprecated] Display our complete proofing guidelines."""
    return render_template("proofing/complete-guide.html")


@bp.route("/help/proofing-guide")
def guidelines():
    """Display our complete proofing guidelines."""
    return render_template("proofing/guidelines.html")


@bp.route("/create-project", methods=["GET", "POST"])
@p2_required
def create_project():
    form = CreateProjectForm()
    if not form.validate_on_submit():
        return render_template("proofing/create-project.html", form=form)

    pdf_source = form.pdf_source.data

    # if pdf_source == "gdrive":
    #     gdrive_folder_url = form.gdrive_folder_url.data
    #     task = project_tasks.create_projects_from_gdrive_folder.delay(
    #         folder_url=gdrive_folder_url,
    #         app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
    #         creator_id=current_user.id,
    #         upload_folder=current_app.config["UPLOAD_FOLDER"],
    #     )
    #     return render_template(
    #         "proofing/create-project-post.html",
    #         stauts=task.status,
    #         current=0,
    #         total=0,
    #         percent=0,
    #         task_id=task.id,
    #     )

    display_title = form.display_title.data or None

    if pdf_source == "multi_url":
        raw_lines = form.pdf_urls.data or ""
        lines = [l.strip() for l in raw_lines.splitlines() if l.strip()]
        if not lines:
            flash("Please provide at least one entry.")
            return render_template("proofing/create-project.html", form=form)

        urls = []
        titles = []
        for i, line in enumerate(lines, start=1):
            if "|" not in line:
                flash(f"Line {i}: expected format 'Title | URL' but no '|' found.")
                return render_template("proofing/create-project.html", form=form)
            title_part, url_part = line.split("|", 1)
            title_part = title_part.strip()
            url_part = url_part.strip()
            if not title_part:
                flash(f"Line {i}: title is missing.")
                return render_template("proofing/create-project.html", form=form)
            if not url_part:
                flash(f"Line {i}: URL is missing.")
                return render_template("proofing/create-project.html", form=form)
            titles.append(title_part)
            urls.append(url_part)

        task = project_tasks.create_projects_from_urls.apply_async(
            kwargs=dict(
                pdf_urls=urls,
                display_titles=titles,
                creator_id=current_user.id,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
        return redirect(url_for("proofing.upload_status", task_id=task.id))

    if pdf_source == "url":
        pdf_url = form.pdf_url.data
        task = project_tasks.create_project_from_url.apply_async(
            kwargs=dict(
                pdf_url=pdf_url,
                display_title=display_title,
                creator_id=current_user.id,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
    else:
        # We accept only PDFs, so validate that the user hasn't uploaded some
        # other kind of document format.
        filename = form.local_file.raw_data[0].filename
        if not _is_allowed_document_file(filename):
            flash("Please upload a PDF.")
            return render_template("proofing/create-project.html", form=form)

        file_data = form.local_file.data
        file_data.seek(0, 2)
        size = file_data.tell()
        file_data.seek(0)
        if size > 128 * 1024 * 1024:
            flash("PDF must be under 128 MB.")
            return render_template("proofing/create-project.html", form=form)

        # Create all directories for this project ahead of time.
        # FIXME(arun): push this further into the Celery task.
        upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "pdf-upload"
        upload_dir.mkdir(parents=True, exist_ok=True)

        temp_id = str(uuid.uuid4())
        pdf_path = upload_dir / f"{temp_id}.pdf"
        form.local_file.data.save(pdf_path)

        task = project_tasks.create_project_from_local_pdf.apply_async(
            kwargs=dict(
                pdf_path=str(pdf_path),
                display_title=display_title,
                creator_id=current_user.id,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
    return redirect(url_for("proofing.upload_status", task_id=task.id))


@bp.route("/upload-status/<task_id>")
def upload_status(task_id):
    """Full status page for a project upload task.

    The task ID is in the URL so users can bookmark or share this page.
    """
    return render_template(
        "proofing/create-project-post.html",
        task_id=task_id,
    )


@bp.route("/check-title")
def check_title():
    """AJAX endpoint: check if a project with a similar title already exists."""
    title = request.args.get("title", "").strip()
    if not title:
        return jsonify(exists=False, slug="")
    slug = slugify(title)
    session = q.get_session()
    existing = session.scalars(select(db.Project).filter_by(slug=slug)).first()
    return jsonify(exists=existing is not None, slug=slug)


@bp.route("/status/<task_id>")
def create_project_status(task_id):
    """AJAX summary of the task."""
    from ambuda.tasks import app as celery_app
    from ambuda.tasks.utils import get_redis

    r = celery_app.AsyncResult(task_id)

    info = r.info or {}
    completed_projects = []
    multi_upload = False
    queue_length = 0

    error_message = None
    if isinstance(info, Exception):
        current = total = percent = 0
        slug = None
        upload_current = upload_total = upload_percent = 0
        error_message = (
            f"{type(info).__name__}: {info}" if str(info) else type(info).__name__
        )
    else:
        current = info.get("current", 100)
        total = info.get("total", 100)
        slug = info.get("slug", None)
        percent = 100 * current / total if total else 0
        upload_current = info.get("upload_current", 0)
        upload_total = info.get("upload_total", 0)
        upload_percent = 100 * upload_current / upload_total if upload_total else 0
        completed_projects = info.get("completed_projects", [])
        multi_upload = info.get("multi_upload", False)

    if r.status == "PENDING":
        try:
            redis_client = get_redis()
            queue_length = redis_client.llen("celery")
        except Exception:
            queue_length = 0

    return render_template(
        "include/task-progress.html",
        status=r.status,
        current=current,
        total=total,
        percent=percent,
        slug=slug,
        upload_current=upload_current,
        upload_total=upload_total,
        upload_percent=upload_percent,
        completed_projects=completed_projects,
        multi_upload=multi_upload,
        queue_length=queue_length,
        error_message=error_message,
    )


def _revision_load_options():
    return (
        orm.defer(db.Revision.content),
        orm.selectinload(db.Revision.author).load_only(db.User.username),
        orm.selectinload(db.Revision.page).load_only(db.Page.slug),
        orm.selectinload(db.Revision.project).load_only(
            db.Project.slug, db.Project.display_title
        ),
        orm.selectinload(db.Revision.status).load_only(db.PageStatus.name),
    )


def _get_recent_activity(
    num_per_page: int,
    before: datetime | None = None,
    after: datetime | None = None,
):
    """Return (activity_list, has_more) for cursor-based pagination."""
    bot_user = q.user(consts.BOT_USERNAME)
    assert bot_user, "Bot user not defined"

    session = q.get_session()

    if after:
        time_filter = lambda col: col > after  # noqa: E731
        order = lambda col: col.asc()  # noqa: E731
    else:
        time_filter = (lambda col: col < before) if before else None  # noqa: E731
        order = lambda col: col.desc()  # noqa: E731

    individual_stmt = (
        select(db.Revision)
        .options(*_revision_load_options())
        .filter(db.Revision.author_id != bot_user.id)
        .filter(db.Revision.batch_id.is_(None))
        .order_by(order(db.Revision.created_at))
        .limit(num_per_page)
    )
    if time_filter:
        individual_stmt = individual_stmt.filter(time_filter(db.Revision.created_at))
    recent_activity = [
        ("revision", r.created, r) for r in session.scalars(individual_stmt)
    ]

    batch_stmt = (
        select(
            db.Revision.batch_id,
            func.count().label("revision_count"),
            func.max(db.Revision.created_at).label("latest_created_at"),
        )
        .filter(db.Revision.author_id != bot_user.id)
        .filter(db.Revision.batch_id.isnot(None))
        .group_by(db.Revision.batch_id)
        .order_by(order(func.max(db.Revision.created_at)))
        .limit(num_per_page)
    )
    if time_filter:
        batch_stmt = batch_stmt.having(time_filter(func.max(db.Revision.created_at)))
    batch_rows = session.execute(batch_stmt).all()
    if batch_rows:
        batch_counts = {row.batch_id: row.revision_count for row in batch_rows}
        latest_per_batch = (
            select(
                db.Revision.batch_id,
                func.max(db.Revision.id).label("max_id"),
            )
            .filter(db.Revision.batch_id.in_(list(batch_counts.keys())))
            .group_by(db.Revision.batch_id)
            .subquery()
        )
        rep_stmt = (
            select(db.Revision)
            .join(latest_per_batch, db.Revision.id == latest_per_batch.c.max_id)
            .options(*_revision_load_options())
        )
        for r in session.scalars(rep_stmt):
            recent_activity.append(("batch", r.created, r, batch_counts[r.batch_id]))

    project_stmt = (
        select(db.Project)
        .options(orm.selectinload(db.Project.creator).load_only(db.User.username))
        .order_by(order(db.Project.created_at))
        .limit(num_per_page)
    )
    if time_filter:
        project_stmt = project_stmt.filter(time_filter(db.Project.created_at))
    recent_activity += [
        ("project", p.created_at, p) for p in session.scalars(project_stmt)
    ]

    recent_activity.sort(key=lambda x: x[1], reverse=True)
    has_more = len(recent_activity) > num_per_page
    return recent_activity[:num_per_page], has_more


def _parse_cursor() -> tuple[datetime | None, datetime | None]:
    try:
        if before := request.args.get("before"):
            return datetime.fromisoformat(before), None
        if after := request.args.get("after"):
            return None, datetime.fromisoformat(after)
    except ValueError:
        pass
    return None, None


@bp.route("/recent-changes")
def recent_changes():
    """Show recent changes across all projects."""
    num_per_page = 100
    before, after = _parse_cursor()

    recent_activity, has_more = _get_recent_activity(
        num_per_page=num_per_page, before=before, after=after
    )

    next_cursor = prev_cursor = None
    if recent_activity:
        oldest_ts = recent_activity[-1][1].isoformat()
        newest_ts = recent_activity[0][1].isoformat()
        if after:
            next_cursor = oldest_ts
            prev_cursor = newest_ts if has_more else None
        else:
            next_cursor = oldest_ts if has_more else None
            prev_cursor = newest_ts if before else None

    return render_template(
        "proofing/recent-changes.html",
        recent_activity=recent_activity,
        next_cursor=next_cursor,
        prev_cursor=prev_cursor,
    )


@bp.route("/batch/<int:batch_id>")
def batch_detail(batch_id):
    """Show all revisions in a batch."""
    session = q.get_session()
    revisions = list(
        session.scalars(
            select(db.Revision)
            .options(*_revision_load_options())
            .filter(db.Revision.batch_id == batch_id)
            .order_by(db.Revision.created_at.desc())
        ).all()
    )
    if not revisions:
        abort(404)

    return render_template(
        "proofing/batch-detail.html",
        revisions=revisions,
        batch_id=batch_id,
    )


@bp.route("/talk")
def talk():
    """Show discussion across all projects."""
    projects = q.active_projects()

    all_threads = [(p, t) for p in projects for t in p.board.threads]
    all_threads.sort(key=lambda x: x[1].updated_at, reverse=True)

    return render_template("proofing/talk.html", all_threads=all_threads)


@bp.route("/texts")
def texts():
    """List all published texts."""

    session = q.get_session()

    page = max(1, request.args.get("page", 1, type=int))
    per_page = 100
    search = request.args.get("q", "", type=str).strip()
    sort_field = request.args.get("sort", "title", type=str)
    sort_dir = request.args.get("sort_dir", "asc", type=str)
    unproofed_only = request.args.get("unproofed", "", type=str) == "1"
    stage = request.args.get("stage", "", type=str).strip()
    project_id = request.args.get("project_id", 0, type=int)
    collection_id = request.args.get("collection_id", 0, type=int)

    if sort_field not in ("title", "project", "created"):
        sort_field = "title"
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    # Fetch texts with their latest validation report in a single query.
    latest_report = (
        select(db.TextReport.id)
        .where(db.TextReport.text_id == db.Text.id)
        .order_by(db.TextReport.created_at.desc())
        .limit(1)
        .correlate(db.Text)
        .scalar_subquery()
    )
    stmt = (
        select(db.Text, db.TextReport)
        .outerjoin(db.TextReport, db.TextReport.id == latest_report)
        .options(
            orm.selectinload(db.Text.project).load_only(
                db.Project.slug, db.Project.display_title
            ),
            orm.selectinload(db.Text.author).load_only(db.Author.name),
            orm.selectinload(db.Text.collections),
        )
    )

    # For search, normalize the query and match against all text titles in Python
    # so that Devanagari, IAST, and HK queries all work interchangeably.
    search_ids = None
    if search:
        norm_query = normalize_for_search(search)
        id_title_rows = session.execute(select(db.Text.id, db.Text.title)).all()
        search_ids = [
            tid
            for tid, title in id_title_rows
            if norm_query in normalize_for_search(title)
        ]
        stmt = stmt.where(db.Text.id.in_(search_ids))

    if stage in ("public", "stub"):
        stmt = stmt.where(db.Text.stage == stage)
    if unproofed_only:
        stmt = stmt.where(db.Text.status == db.TextStatus.P0)
    if project_id:
        stmt = stmt.where(db.Text.project_id == project_id)
    if collection_id:
        stmt = stmt.where(
            db.Text.collections.any(db.TextCollection.id == collection_id)
        )

    sort_column = {
        "title": db.Text.title,
        "project": db.Project.display_title,
        "created": db.Text.created_at,
    }[sort_field]
    if sort_field == "project":
        stmt = stmt.outerjoin(db.Project, db.Text.project_id == db.Project.id)
    direction = asc if sort_dir == "asc" else desc
    stmt = stmt.order_by(direction(sort_column))

    # Count total before pagination.
    count_stmt = select(func.count()).select_from(db.Text)
    if search_ids is not None:
        count_stmt = count_stmt.where(db.Text.id.in_(search_ids))
    if stage in ("public", "stub"):
        count_stmt = count_stmt.where(db.Text.stage == stage)
    if unproofed_only:
        count_stmt = count_stmt.where(db.Text.status == db.TextStatus.P0)
    if project_id:
        count_stmt = count_stmt.where(db.Text.project_id == project_id)
    if collection_id:
        count_stmt = count_stmt.where(
            db.Text.collections.any(db.TextCollection.id == collection_id)
        )
    total = session.execute(count_stmt).scalar()
    total_pages = ceil(total / per_page) if total > 0 else 1

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    rows = session.execute(stmt).all()

    # Build a flat list of (text, parsed_report) pairs.
    report_map = {}
    all_texts = []
    for t, tr in rows:
        all_texts.append(t)
        if tr:
            report_map[t.id] = try_parse_text_report(tr.payload)

    # Map text_id → (project_slug) for texts that have a publish config.
    text_ids = [t.id for t in all_texts]
    config_map = {}
    if text_ids:
        config_rows = (
            session.query(
                db.PublishConfig.text_id,
                db.Project.slug,
            )
            .join(db.Project, db.PublishConfig.project_id == db.Project.id)
            .filter(db.PublishConfig.text_id.in_(text_ids))
            .all()
        )
        for text_id, project_slug in config_rows:
            config_map[text_id] = project_slug

    template_vars = dict(
        all_texts=all_texts,
        report_map=report_map,
        config_map=config_map,
        page=page,
        total=total,
        total_pages=total_pages,
        search=search,
        sort_field=sort_field,
        sort_dir=sort_dir,
        unproofed_only=unproofed_only,
        stage=stage,
        project_id=project_id,
        collection_id=collection_id,
    )

    if request.args.get("partial"):
        html = render_template("proofing/texts_table.html", **template_vars)
        return jsonify(html=html, total=total)

    # Fetch projects that have at least one text, for the filter dropdown.
    filter_projects = (
        session.query(db.Project)
        .filter(db.Project.texts.any())
        .order_by(db.Project.display_title)
        .all()
    )
    template_vars["filter_projects"] = filter_projects

    filter_collections = (
        session.query(db.TextCollection)
        .filter(db.TextCollection.texts.any())
        .order_by(db.TextCollection.title)
        .all()
    )
    template_vars["filter_collections"] = filter_collections

    return render_template("proofing/texts.html", **template_vars)


@bp.route("/texts/new", methods=["GET", "POST"])
@p2_required
def create_text():
    """Create a new stub Text + PublishConfig from a single form."""
    from ambuda.models.proofing import LanguageCode, PublishConfig
    from ambuda.models.texts import TextStage
    from ambuda.utils.text_publishing import Filter
    from ambuda.utils.slug import title_to_slug
    from ambuda.views.proofing.publish import _validate_slug

    session = q.get_session()

    projects = session.query(db.Project).order_by(db.Project.display_title).all()
    all_collections = (
        session.query(db.TextCollection).order_by(db.TextCollection.title).all()
    )

    form = CreateTextForm()
    form.project_id.choices = [(p.id, p.display_title) for p in projects]
    form.language.choices = [(c.value, c.label) for c in LanguageCode]

    def _render():
        return render_template(
            "proofing/texts_new.html",
            form=form,
            projects=projects,
            all_collections=all_collections,
            collection_ids=collection_ids,
        )

    collection_ids: list[int] = []
    if request.method == "POST":
        collection_ids = [
            int(c) for c in request.form.getlist("collection_ids") if c.isdigit()
        ]

        if not form.validate_on_submit():
            return _render()

        slug = form.slug.data.strip()
        slug_error = _validate_slug(slug)
        if slug_error:
            flash(slug_error, "error")
            return _render()

        existing_text = session.execute(
            select(db.Text).where(db.Text.slug == slug)
        ).scalar_one_or_none()
        if existing_text:
            flash(
                f"A text with slug '{slug}' already exists. "
                "Please choose a different slug.",
                "error",
            )
            return _render()

        target = (form.target.data or "").strip()
        try:
            if target.startswith("("):
                Filter(target)
            else:
                Filter(f"(label {target})")
        except ValueError as e:
            flash(f"Invalid filter: {e}", "error")
            return _render()

        project = session.get(db.Project, form.project_id.data)
        if project is None:
            flash("Selected project does not exist.", "error")
            return _render()

        parent_id = None
        parent_slug = (form.parent_slug.data or "").strip()
        if parent_slug:
            parent_text = session.execute(
                select(db.Text).where(db.Text.slug == parent_slug)
            ).scalar_one_or_none()
            if parent_text is None:
                flash(f"Parent slug '{parent_slug}' does not exist.", "error")
                return _render()
            parent_id = parent_text.id

        author_id = None
        author_name = (form.author.data or "").strip()
        if author_name:
            author = session.execute(
                select(db.Author).where(db.Author.name == author_name)
            ).scalar_one_or_none()
            if not author:
                author = db.Author(name=author_name, slug=title_to_slug(author_name))
                session.add(author)
                session.flush()
            author_id = author.id

        text = db.Text(
            slug=slug,
            title=form.title.data.strip(),
            language=form.language.data or "sa",
            stage=TextStage.STUB,
            project_id=project.id,
            author_id=author_id,
            parent_id=parent_id,
        )
        if collection_ids:
            colls = (
                session.query(db.TextCollection)
                .filter(db.TextCollection.id.in_(collection_ids))
                .all()
            )
            text.collections = list(colls)
        session.add(text)
        session.flush()

        session.add(
            PublishConfig(
                project_id=project.id,
                text_id=text.id,
                target=target,
            )
        )
        session.commit()

        flash(f"Created text '{text.title}'.", "success")
        return redirect(url_for("proofing.publish.config", slug=project.slug))

    return _render()


@bp.route("/texts/<slug>/report")
def text_report(slug):
    """Show validation report for a text."""

    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    text_report_ = q.text_report(text.id)
    report = None
    updated_at = None
    if text_report_:
        report = try_parse_text_report(text_report_.payload)
        updated_at = text_report_.updated_at
    return render_template(
        "proofing/text-report.html",
        text=text,
        report=report,
        form=FlaskForm(),
        updated_at=updated_at,
    )


@bp.route("/texts/<slug>/report/rerun", methods=["POST"])
@p2_required
def rerun_text_report(slug):
    """Trigger a re-run of the validation report for a text."""
    from ambuda.tasks.text_validation import maybe_rerun_report

    text = q.text(slug)
    if text is None:
        abort(404)

    if maybe_rerun_report(text.id, current_app.config["AMBUDA_ENVIRONMENT"]):
        flash("Report re-run started. Refresh in a moment to see updated results.")
    else:
        flash("A report re-run is already in progress.")
    return redirect(url_for("proofing.text_report", slug=slug))


def _project_coverage_summary(project) -> dict:
    """Cheap, image-range-only coverage check for one project.

    Returns the count of pages with status R1/R2 whose image number falls
    outside the union of image ranges of all *public* PublishConfig filters
    on this project. Filters that don't have a clean image range (label-only,
    OR/NOT, etc.) bump ``has_unbounded_filter`` so admins can drill down for
    a precise count.
    """
    from ambuda.enums import SitePageStatus
    from ambuda.models.proofing import PublishConfig
    from ambuda.models.texts import TextStage
    from ambuda.utils.text_publishing import Filter

    public_configs = [
        pc
        for pc in project.publish_configs
        if pc.text is not None and pc.text.stage == TextStage.PUBLIC
    ]

    covered: set[int] = set()
    has_unbounded_filter = False
    for pc in public_configs:
        target = (pc.target or "").strip()
        if not target:
            # Empty target ≈ "matches everything" — treat as unbounded.
            has_unbounded_filter = True
            continue
        try:
            f = Filter(target if target.startswith("(") else f"(label {target})")
        except ValueError:
            continue
        rng = f.image_range()
        if rng is None:
            has_unbounded_filter = True
            continue
        for img in range(rng[0], rng[1] + 1):
            covered.add(img)

    proofed_status_names = {SitePageStatus.R1, SitePageStatus.R2}
    proofed_count = 0
    uncovered_count = 0
    for i, page in enumerate(project.pages):
        image_number = i + 1
        if page.status.name in proofed_status_names:
            proofed_count += 1
            if image_number not in covered:
                uncovered_count += 1

    return {
        "proofed_count": proofed_count,
        "uncovered_count": uncovered_count,
        "has_unbounded_filter": has_unbounded_filter,
        "num_public_configs": len(public_configs),
    }


@bp.route("/admin/unpublished-projects")
@p2_required
def unpublished_projects():
    """List projects with proofed pages outside any public filter's image range.

    Cheap inline pass: image-range-only, computed on each request. For exact
    block-level details, drill into a project (which uses the cached Celery
    report instead).
    """
    session = q.get_session()
    projects = (
        session.query(db.Project)
        .options(
            orm.selectinload(db.Project.publish_configs).selectinload(
                db.PublishConfig.text
            ),
            orm.selectinload(db.Project.pages).selectinload(db.Page.status),
        )
        .order_by(db.Project.display_title)
        .all()
    )

    reports_by_project = {
        r.project_id: r for r in session.query(db.ProjectUncoveredReport).all()
    }

    rows = []
    all_rows = []
    for project in projects:
        summary = _project_coverage_summary(project)
        report = reports_by_project.get(project.id)
        row = {
            "project": project,
            "report": report,
            "report_block_count": (
                len(report.payload.get("blocks", [])) if report else None
            ),
            **summary,
        }
        all_rows.append(row)
        if summary["uncovered_count"] > 0 or summary["has_unbounded_filter"]:
            rows.append(row)

    return render_template(
        "proofing/unpublished_projects.html",
        rows=rows,
        all_rows=all_rows,
        form=FlaskForm(),
    )


@bp.route("/admin/unpublished-projects/refresh-all", methods=["POST"])
@p2_required
def refresh_all_unpublished_reports():
    """Dispatch a Celery task to recompute the report for every project."""
    from ambuda.tasks.uncovered_reports import maybe_rerun_report

    session = q.get_session()
    project_ids = [pid for (pid,) in session.query(db.Project.id).all()]

    app_env = current_app.config["AMBUDA_ENVIRONMENT"]
    dispatched = 0
    skipped = 0
    for pid in project_ids:
        if maybe_rerun_report(pid, app_env):
            dispatched += 1
        else:
            skipped += 1

    flash(
        f"Dispatched {dispatched} report task(s); {skipped} already in progress.",
        "info",
    )
    return redirect(url_for("proofing.unpublished_projects"))


@bp.route("/admin/unpublished-projects/<slug>")
@p2_required
def unpublished_project_detail(slug):
    """Per-project drill-down: shows the cached uncovered-blocks report."""
    project = q.project(slug)
    if project is None:
        abort(404)

    session = q.get_session()
    report = (
        session.query(db.ProjectUncoveredReport)
        .filter_by(project_id=project.id)
        .one_or_none()
    )
    blocks = report.payload.get("blocks", []) if report else []

    return render_template(
        "proofing/unpublished_project_detail.html",
        project=project,
        report=report,
        blocks=blocks,
        form=FlaskForm(),
    )


@bp.route("/admin/unpublished-projects/<slug>/refresh", methods=["POST"])
@p2_required
def refresh_unpublished_project_report(slug):
    """Trigger a Celery task to recompute the uncovered-blocks report."""
    from ambuda.tasks.uncovered_reports import maybe_rerun_report

    project = q.project(slug)
    if project is None:
        abort(404)

    if maybe_rerun_report(project.id, current_app.config["AMBUDA_ENVIRONMENT"]):
        flash(
            "Report refresh started. Reload in a moment to see updated results.",
            "info",
        )
    else:
        flash("A report refresh is already in progress for this project.", "info")
    return redirect(url_for("proofing.unpublished_project_detail", slug=slug))


@bp.route("/admin/dashboard/")
@moderator_required
def admin_dashboard():
    now = datetime.now(UTC).replace(tzinfo=None)
    days_ago_30d = now - timedelta(days=30)
    days_ago_7d = now - timedelta(days=7)
    days_ago_1d = now - timedelta(days=1)

    session = q.get_session()
    stmt = select(db.User).filter_by(username=consts.BOT_USERNAME)
    bot = session.scalars(stmt).one()
    bot_id = bot.id

    stmt = (
        select(db.Revision)
        .filter(
            (db.Revision.created_at >= days_ago_30d) & (db.Revision.author_id != bot_id)
        )
        .options(orm.load_only(db.Revision.created_at, db.Revision.author_id))
        .order_by(db.Revision.created_at)
    )
    revisions_30d = list(session.scalars(stmt).all())
    revisions_7d = [x for x in revisions_30d if x.created >= days_ago_7d]
    revisions_1d = [x for x in revisions_7d if x.created >= days_ago_1d]
    num_revisions_30d = len(revisions_30d)
    num_revisions_7d = len(revisions_7d)
    num_revisions_1d = len(revisions_1d)

    num_contributors_30d = len({x.author_id for x in revisions_30d})
    num_contributors_7d = len({x.author_id for x in revisions_7d})
    num_contributors_1d = len({x.author_id for x in revisions_1d})

    return render_template(
        "proofing/dashboard.html",
        num_revisions_30d=num_revisions_30d,
        num_revisions_7d=num_revisions_7d,
        num_revisions_1d=num_revisions_1d,
        num_contributors_30d=num_contributors_30d,
        num_contributors_7d=num_contributors_7d,
        num_contributors_1d=num_contributors_1d,
    )


@bp.route("/texts/batch-collections", methods=["GET", "POST"])
@p2_required
def batch_edit_collections():
    """Add or remove collections for selected texts."""
    session = q.get_session()
    text_ids = request.args.getlist("text_id", type=int) or request.form.getlist(
        "text_id", type=int
    )
    if not text_ids:
        flash("No texts selected.", "error")
        return redirect(url_for("proofing.texts"))

    selected_texts = session.query(db.Text).filter(db.Text.id.in_(text_ids)).all()
    all_collections_flat = (
        session.query(db.TextCollection)
        .options(orm.selectinload(db.TextCollection.parent))
        .all()
    )
    # Build a nested tree sorted alphabetically at each level.
    by_parent: dict[int | None, list] = {}
    for c in all_collections_flat:
        by_parent.setdefault(c.parent_id, []).append(c)
    for children in by_parent.values():
        children.sort(key=lambda c: c.title)

    all_collections = []

    def _walk(parent_id, depth):
        for c in by_parent.get(parent_id, []):
            all_collections.append((c, depth))
            _walk(c.id, depth + 1)

    _walk(None, 0)

    # Map child_id → parent_id for the JS auto-select behaviour.
    parent_map = {c.id: c.parent_id for c in all_collections_flat if c.parent_id}

    # Map id → set of all descendant ids, for de-duping on save.
    def _descendants(pid):
        result = set()
        for c in by_parent.get(pid, []):
            result.add(c.id)
            result |= _descendants(c.id)
        return result

    descendant_map = {c.id: _descendants(c.id) for c in all_collections_flat}

    form = FlaskForm()
    if form.validate_on_submit():
        add_ids = set(request.form.getlist("add_collection", type=int))
        remove_ids = set(request.form.getlist("remove_collection", type=int))

        # De-dupe: if a descendant is selected, drop its ancestors.
        add_ids = {
            cid for cid in add_ids if not (descendant_map.get(cid, set()) & add_ids)
        }
        remove_ids = {
            cid
            for cid in remove_ids
            if not (descendant_map.get(cid, set()) & remove_ids)
        }

        add_collections = (
            session.query(db.TextCollection)
            .filter(db.TextCollection.id.in_(add_ids))
            .all()
            if add_ids
            else []
        )
        remove_collections = (
            session.query(db.TextCollection)
            .filter(db.TextCollection.id.in_(remove_ids))
            .all()
            if remove_ids
            else []
        )

        for text in selected_texts:
            for coll in add_collections:
                if coll not in text.collections:
                    text.collections.append(coll)
            for coll in remove_collections:
                if coll in text.collections:
                    text.collections.remove(coll)

        session.commit()
        flash(f"Updated collections for {len(selected_texts)} text(s).", "success")
        return redirect(url_for("proofing.texts"))

    return render_template(
        "proofing/batch_collections.html",
        form=form,
        selected_texts=selected_texts,
        all_collections=all_collections,
        parent_map=parent_map,
        text_ids=text_ids,
    )
