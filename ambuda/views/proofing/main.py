"""Views for basic site pages."""

from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, flash, render_template
from flask_login import current_user
from flask_wtf import FlaskForm
from slugify import slugify
from sqlalchemy import orm
from wtforms import FileField, RadioField, StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import consts
from ambuda import queries as q
from ambuda.database import Page, Project, Revision, User
from ambuda.enums import SitePageStatus
from ambuda.models.base import db
from ambuda.tasks import projects as project_tasks
from ambuda.views.proofing.decorators import moderator_required, p2_required

bp = Blueprint("proofing", __name__)


def _is_allowed_document_file(filename: str) -> bool:
    """True iff we accept this type of document upload."""
    return Path(filename).suffix == ".pdf"


def _required_if_archive(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "archive.org" and not field.data:
            raise ValidationError(message)

    return fn


def _required_if_local(message: str):
    def fn(form, field):
        source = form.pdf_source.data
        if source == "local" and not field.data:
            raise ValidationError(message)

    return fn


class CreateProjectForm(FlaskForm):
    pdf_source = RadioField(
        "Source",
        choices=[
            ("archive.org", "From archive.org"),
            ("local", "From my computer"),
        ],
        validators=[DataRequired()],
    )
    archive_identifier = StringField(
        "archive.org identifier",
        validators=[
            _required_if_archive("Please provide a valid archive.org identifier.")
        ],
    )
    local_file = FileField(
        "PDF file", validators=[_required_if_local("Please provide a PDF file.")]
    )
    local_title = StringField(
        "Title of the book (you can change this later)",
        validators=[
            _required_if_local(
                "Please provide a title for your PDF.",
            )
        ],
    )

    license = RadioField(
        "License",
        choices=[
            ("public", "Public domain"),
            ("copyrighted", "Copyrighted"),
            ("other", "Other"),
        ],
        validators=[DataRequired()],
    )
    custom_license = StringField(
        "License",
        widget=TextArea(),
        render_kw={
            "placeholder": "Please tell us about this book's license.",
        },
    )


@bp.route("/")
def index():
    """List all available proofing projects."""

    # Fetch all project data in a single query for better performance.
    session = q.get_session()
    projects = (
        session.query(Project)
        .options(
            orm.joinedload(Project.pages).load_only(Page.id).joinedload(Page.status)
        )
        .all()
    )
    status_classes = {
        SitePageStatus.R2: "bg-green-200",
        SitePageStatus.R1: "bg-yellow-200",
        SitePageStatus.R0: "bg-red-300",
        SitePageStatus.SKIP: "bg-slate-100",
    }

    projects = q.projects()
    statuses_per_project = {}
    progress_per_project = {}
    pages_per_project = {}
    for project in projects:
        page_statuses = [p.status.name for p in project.pages]

        # FIXME(arun): catch this properly, prevent prod issues
        if not page_statuses:
            statuses_per_project[project.id] = {}
            pages_per_project[project.id] = 0
            continue

        num_pages = len(page_statuses)
        project_counts = {}
        for enum_value, class_ in status_classes.items():
            fraction = page_statuses.count(enum_value) / num_pages
            project_counts[class_] = fraction
            if enum_value == SitePageStatus.R0:
                # The more red pages there are, the lower progress is.
                progress_per_project[project.id] = 1 - fraction

        statuses_per_project[project.id] = project_counts
        pages_per_project[project.id] = num_pages

    projects.sort(key=lambda x: x.title)
    return render_template(
        "proofing/index.html",
        projects=projects,
        statuses_per_project=statuses_per_project,
        progress_per_project=progress_per_project,
        pages_per_project=pages_per_project,
    )


@bp.route("/help/beginners-guide")
def beginners_guide():
    """Display our minimal proofing guidelines."""
    return render_template("proofing/beginners-guide.html")


@bp.route("/help/complete-guide")
def complete_guide():
    """Display our complete proofing guidelines."""
    return render_template("proofing/complete-guide.html")


@bp.route("/help/editor-guide")
def editor_guide():
    """Describe how to use the page editor."""
    return render_template("proofing/editor-guide.html")


@bp.route("/create-project", methods=["GET", "POST"])
@p2_required
def create_project():
    form = CreateProjectForm()
    if form.validate_on_submit():
        title = form.local_title.data

        # TODO: add timestamp to slug for extra uniqueness?
        slug = slugify(title)

        # We accept only PDFs, so validate that the user hasn't uploaded some
        # other kind of document format.
        filename = form.local_file.raw_data[0].filename
        if not _is_allowed_document_file(filename):
            flash("Please upload a PDF.")
            return render_template("proofing/create-project.html", form=form)

        # Create all directories for this project ahead of time.
        # FIXME(arun): push this further into the Celery task.
        project_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "projects" / slug
        pdf_dir = project_dir / "pdf"
        page_image_dir = project_dir / "pages"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        page_image_dir.mkdir(parents=True, exist_ok=True)

        # Save the original PDF so that it can be downloaded later or reused
        # for future tasks (thumbnails, better image formats, etc.)
        pdf_path = pdf_dir / "source.pdf"
        form.local_file.data.save(pdf_path)

        task = project_tasks.create_project.delay(
            title=title,
            pdf_path=str(pdf_path),
            output_dir=str(page_image_dir),
            creator_id=current_user.id,
        )
        return render_template(
            "proofing/create-project-post.html",
            stauts=task.status,
            current=0,
            total=0,
            percent=0,
            task_id=task.id,
        )

    return render_template("proofing/create-project.html", form=form)


@bp.route("/status/<task_id>")
def create_project_status(task_id):
    """AJAX summary of the task."""
    r = project_tasks.create_project.AsyncResult(task_id)

    info = r.info or {}
    if isinstance(info, Exception):
        current = total = percent = 0
        slug = None
    else:
        current = info.get("current", 100)
        total = info.get("total", 100)
        slug = info.get("slug", None)
        percent = 100 * current / total

    return render_template(
        "include/task-progress.html",
        status=r.status,
        current=current,
        total=total,
        percent=percent,
        slug=slug,
    )


@bp.route("/recent-changes")
def recent_changes():
    """Show recent changes across all projects."""
    per_page = 50

    # Exclude bot edits, which overwhelm all other edits on the site.
    bot_user = q.user(consts.BOT_USERNAME)
    assert bot_user, "Bot user not defined"

    q.get_session()
    recent_revisions = db.paginate(
        db.select(Revision)
        # Defer slow columns
        .options(orm.defer(Revision.content))
        # Avoid bot changes, which dominate the logs.
        .filter(Revision.author_id != bot_user.id).order_by(Revision.created.desc()),
        per_page=per_page,
        max_per_page=per_page,
    )

    return render_template(
        "proofing/recent-changes.html", recent_revisions=recent_revisions
    )


@bp.route("/talk")
def talk():
    """Show discussion across all projects."""
    projects = q.projects()

    # FIXME: optimize this once we have a higher thread volume.
    all_threads = [(p, t) for p in projects for t in p.board.threads]
    all_threads.sort(key=lambda x: x[1].updated_at, reverse=True)

    return render_template("proofing/talk.html", all_threads=all_threads)


@bp.route("/admin/dashboard/")
@moderator_required
def dashboard():
    now = datetime.now()
    days_ago_30d = now - timedelta(days=30)
    days_ago_7d = now - timedelta(days=7)
    days_ago_1d = now - timedelta(days=1)

    session = q.get_session()
    bot = session.query(User).filter_by(username=consts.BOT_USERNAME).one()
    bot_id = bot.id

    revisions_30d = (
        session.query(Revision)
        .filter((Revision.created >= days_ago_30d) & (Revision.author_id != bot_id))
        .options(orm.load_only(Revision.created, Revision.author_id))
        .order_by(Revision.created)
        .all()
    )
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
