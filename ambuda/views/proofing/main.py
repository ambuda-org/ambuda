"""Views for basic site pages."""

from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from slugify import slugify
from sqlalchemy import orm
from wtforms import StringField, FileField
from wtforms.validators import DataRequired

from ambuda import consts
from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SiteRole, SitePageStatus
from ambuda.tasks import projects as project_tasks
from ambuda.views.proofing.decorators import p2_required


bp = Blueprint("proofing", __name__)


def _is_allowed_document_file(filename: str) -> bool:
    """True iff we accept this type of document upload."""
    return Path(filename).suffix == ".pdf"


class CreateProjectWithPdfForm(FlaskForm):
    file = FileField("PDF file", validators=[DataRequired()])
    title = StringField(
        "Title of the book (you can change this later)", validators=[DataRequired()]
    )


@bp.route("/")
def index():
    """List all available proofing projects."""

    # Fetch all project data in a single query for better performance.
    session = q.get_session()
    projects = (
        session.query(db.Project)
        .options(
            orm.joinedload(db.Project.pages)
            .load_only(db.Page.id)
            .joinedload(db.Page.status)
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
    form = CreateProjectWithPdfForm()
    if form.validate_on_submit():
        # TODO: timestamp slug?
        slug = slugify(form.title.data)
        project_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "projects" / slug

        pdf_dir = project_dir / "pdf"
        page_image_dir = project_dir / "pages"

        pdf_dir.mkdir(parents=True, exist_ok=True)
        page_image_dir.mkdir(parents=True, exist_ok=True)

        pdf_path = pdf_dir / "source.pdf"
        filename = form.file.raw_data[0].filename
        if not _is_allowed_document_file(filename):
            flash("Please upload a PDF.")
            return render_template("proofing/create-project.html", form=form)
        form.file.data.save(pdf_path)

        task = project_tasks.create_project.delay(
            title=form.title.data,
            pdf_path=str(pdf_path),
            output_dir=str(page_image_dir),
            app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
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
    num_per_page = 100

    # Exclude bot edits, which overwhelm all other edits on the site.
    bot_user = q.user(consts.BOT_USERNAME)
    assert bot_user, "Bot user not defined"

    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision)
        .options(orm.defer(db.Revision.content))
        .filter(db.Revision.author_id != bot_user.id)
        .order_by(db.Revision.created.desc())
        .limit(num_per_page)
        .all()
    )
    recent_activity = [("revision", r.created, r) for r in recent_revisions]

    recent_projects = (
        session.query(db.Project)
        .order_by(db.Project.created_at.desc())
        .limit(num_per_page)
        .all()
    )
    recent_activity += [("project", p.created_at, p) for p in recent_projects]

    recent_activity.sort(key=lambda x: x[1], reverse=True)
    recent_activity = recent_activity[:num_per_page]
    return render_template(
        "proofing/recent-changes.html", recent_activity=recent_activity
    )


@bp.route("/talk")
def talk():
    """Show discussion across all projects."""
    projects = q.projects()

    # FIXME: optimize this once we have a higher thread volume.
    all_threads = [(p, t) for p in projects for t in p.board.threads]
    all_threads.sort(key=lambda x: x[1].updated_at, reverse=True)

    return render_template("proofing/talk.html", all_threads=all_threads)
