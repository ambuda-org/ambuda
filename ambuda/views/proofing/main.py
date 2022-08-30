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

import ambuda.queries as q
from ambuda import database as db
from ambuda.tasks import projects as project_tasks


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

    all_counts = {}
    all_page_counts = {}
    for project in projects:
        page_statuses = [p.status.name for p in project.pages]

        # FIXME(arun): catch this properly, prevent prod issues
        if not page_statuses:
            all_counts[project.slug] = {}
            all_page_counts[project.slug] = 0
            continue

        num_pages = len(page_statuses)
        project_counts = {
            "bg-green-200": page_statuses.count("reviewed-2") / num_pages,
            "bg-yellow-200": page_statuses.count("reviewed-1") / num_pages,
            "bg-red-300": page_statuses.count("reviewed-0") / num_pages,
            "bg-slate-100": page_statuses.count("skip") / num_pages,
        }

        all_counts[project.slug] = project_counts
        all_page_counts[project.slug] = num_pages

    return render_template(
        "proofing/index.html",
        projects=projects,
        all_counts=all_counts,
        all_page_counts=all_page_counts,
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
@login_required
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

        pdf_path = pdf_dir / f"source.pdf"
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
        status = r.status
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
    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision).order_by(db.Revision.created.desc()).limit(100).all()
    )
    return render_template("proofing/recent-changes.html", revisions=recent_revisions)


@bp.route("/talk")
def talk():
    """Show discussion across all projects."""
    session = q.get_session()
    projects = q.projects()

    # FIXME: optimize this once we have a higher thread volume.
    all_threads = [(p, t) for p in projects for t in p.board.threads]
    all_threads.sort(key=lambda x: x[1].updated_at, reverse=True)

    return render_template("proofing/talk.html", all_threads=all_threads)
