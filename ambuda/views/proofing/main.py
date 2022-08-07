"""Views for basic site pages."""

from pathlib import Path

from celery.result import AsyncResult
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    render_template,
    redirect,
    request,
    url_for,
)
from flask_login import login_required
from flask_wtf import FlaskForm
from slugify import slugify
from werkzeug.utils import secure_filename
from wtforms import StringField, FileField
from wtforms.validators import DataRequired

import ambuda.queries as q
from ambuda import database as db
from ambuda.tasks import pdf
from ambuda.views.proofing.utils import _get_image_filesystem_path


bp = Blueprint("proofing", __name__)


def _is_allowed_document_file(filename: str) -> bool:
    """True iff we accept this type of document upload."""
    return Path(filename).suffix == ".pdf"


def _is_allowed_image_file(filename: str) -> bool:
    """True iff we accept this type of image upload."""
    return Path(filename).suffix == ".jpg"


class CreateProjectWithPdfForm(FlaskForm):
    file = FileField("PDF file", validators=[DataRequired()])
    title = StringField(
        "Title of the book (you can change this later)", validators=[DataRequired()]
    )


@bp.route("/")
def index():
    """List all available proofing projects."""
    projects = q.projects()

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


@bp.route("/beginners-guide")
def beginners_guide():
    """Display our minimal proofing guidelines."""
    return render_template("proofing/beginners-guide.html")


@bp.route("/complete-guide")
def complete_guide():
    """Display our complete proofing guidelines."""
    return render_template("proofing/complete-guidelines.html")


@bp.route("/create-project", methods=["GET", "POST"])
@login_required
def create_project():
    form = CreateProjectWithPdfForm()
    if form.validate_on_submit():
        task = pdf.create_project.delay("path.txt")
        info = task.info or {}
        return render_template(
            "proofing/create-project-post.html",
            task_id=task.id,
            current=info.get("current", 0),
            total=info.get("total", 100),
        )

    return render_template("proofing/create-project.html", form=form)


@bp.route("/status/<task_id>")
def create_project_status(task_id):
    # NOTE: use redis backend to allow multi-process fetch.
    status = pdf.create_project.AsyncResult(task_id)
    info = status.info or {}
    print(info)
    return render_template(
        "include/task-progress.html",
        current=info.get("current", 0),
        total=info.get("total", 100),
    )


# Unused in prod -- needs task queue support (celery/dramatiq)
@login_required
def upload_pdf_post():
    if "file" not in request.files:
        # Request has no file data
        flash("Sorry, there's a server error.")
        return redirect(request.url)

    file = request.files["file"]
    if file.filename == "":
        # Empty file submitted.
        flash("Please submit a file.")
        return redirect(request.url)

    title = request.form.get("title", None)
    if not title:
        # Missing title.
        flash("Please submit a title.")
        return redirect(request.url)

    # Check that we have a valid slug.
    # `secure_filename` might be redundant given what `slugify` already does,
    # but let's call it anyway so that we're not coupled to the internals of
    # `slugify` here.
    slug = slugify(title)
    slug = secure_filename(slug)
    if not slug:
        # Slug is empty -- bad title.
        flash("Please submit a valid title.")
        return redirect(request.url)

    if file and _is_allowed_image_file(file.filename):
        pdf_path = Path(current_app.config["UPLOAD_FOLDER"]) / slug / "original.pdf"
        pdf_path.parent.mkdir(exist_ok=True, parents=True)
        file.save(pdf_path)

        q.create_project(title=title, slug=slug)
        # FIXME: Need to fetch again, otherwise DetachedInstanceError?
        # https://sqlalche.me/e/14/bhk3
        project_ = q.project(slug)

        pdf.create_pages.send(project_.id, pdf_path)
        return redirect(url_for("proofing.index"))

    flash("Please submit a PDF file.")
    return redirect(request.url)


@bp.route("/recent-changes")
def recent_changes():
    """Show recent changes across all projects."""
    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision).order_by(db.Revision.created.desc()).limit(100).all()
    )
    return render_template("proofing/recent-changes.html", revisions=recent_revisions)
