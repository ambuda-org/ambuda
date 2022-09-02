from celery.result import GroupResult
from flask import (
    current_app,
    render_template,
    flash,
    url_for,
    make_response,
    request,
    Blueprint,
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from markupsafe import escape, Markup
from sqlalchemy import orm
from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import queries as q, database as db
from ambuda.tasks import ocr as ocr_tasks
from ambuda.tasks import app as celery_app
from ambuda.utils import project_utils
from ambuda.utils import proofing_utils
from ambuda.utils.auth import admin_required


bp = Blueprint("project", __name__)


def _is_valid_page_number_spec(_, field):
    try:
        _ = project_utils.parse_page_number_spec(field.data)
    except Exception:
        raise ValidationError("The page number spec isn't valid.")


class EditMetadataForm(FlaskForm):
    description = StringField(
        "Description (optional)",
        widget=TextArea(),
        render_kw={
            "placeholder": "What is this book about? Why is this project exciting?",
        },
    )
    page_numbers = StringField(
        "Page numbers (optional)",
        widget=TextArea(),
        validators=[_is_valid_page_number_spec],
        render_kw={
            "placeholder": "Coming soon.",
        },
    )
    title = StringField("Title", validators=[DataRequired()])
    author = StringField(
        "Author",
        render_kw={
            "placeholder": "The author of the original work, e.g. Kalidasa.",
        },
    )
    editor = StringField(
        "Editor",
        render_kw={
            "placeholder": "The person or organization that created this edition of the text.",
        },
    )
    publisher = StringField(
        "Publisher",
        render_kw={
            "placeholder": "The original publisher of this book, e.g. Nirnayasagar.",
        },
    )
    publication_year = StringField(
        "Publication year",
        render_kw={
            "placeholder": "The year in which this specific edition was published.",
        },
    )


class SearchForm(FlaskForm):
    class Meta:
        csrf = False

    query = StringField("Query", validators=[DataRequired()])


class DeleteProjectForm(FlaskForm):
    slug = StringField("Slug", validators=[DataRequired()])


@bp.route("/<slug>/")
def summary(slug):
    """Show basic information about the project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision)
        .filter_by(project_id=project_.id)
        .order_by(db.Revision.created.desc())
        .limit(10)
        .all()
    )

    page_rules = project_utils.parse_page_number_spec(project_.page_numbers)
    page_titles = project_utils.apply_rules(len(project_.pages), page_rules)
    return render_template(
        "proofing/projects/summary.html",
        project=project_,
        pages=zip(page_titles, project_.pages),
        recent_revisions=recent_revisions,
    )


@bp.route("/<slug>/activity")
def activity(slug):
    """Show recent activity on this project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision)
        .options(orm.defer(db.Revision.content))
        .filter_by(project_id=project_.id)
        .order_by(db.Revision.created.desc())
        .limit(100)
        .all()
    )
    recent_activity = [("revision", r.created, r) for r in recent_revisions]
    recent_activity.append(("project", project_.created_at, project_))

    return render_template(
        "proofing/projects/activity.html",
        project=project_,
        recent_activity=recent_activity,
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    """Edit the project's metadata."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = EditMetadataForm(obj=project_)
    if form.validate_on_submit():
        session = q.get_session()
        form.populate_obj(project_)
        session.commit()

        flash("Saved changes.", "success")
        return redirect(url_for("proofing.project.summary", slug=slug))

    return render_template(
        "proofing/projects/edit.html",
        project=project_,
        form=form,
    )


@bp.route("/<slug>/download/")
def download(slug):
    """Download the project in various output formats."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    return render_template("proofing/projects/download.html", project=project_)


@bp.route("/<slug>/download/text")
def download_as_text(slug):
    """Download the project as plain text."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    content_blobs = [
        p.revisions[-1].content if p.revisions else "" for p in project_.pages
    ]
    raw_text = proofing_utils.to_plain_text(content_blobs)

    response = make_response(raw_text, 200)
    response.mimetype = "text/plain"
    return response


@bp.route("/<slug>/download/xml")
def download_as_xml(slug):
    """Download the project as TEI XML.

    This XML will likely have various errors, but it is correct enough that it
    still saves a lot of manual work.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    project_meta = {
        "title": project_.title,
        "author": project_.author,
        "publication_year": project_.publication_year,
        "publisher": project_.publisher,
        "editor": project_.editor,
    }
    project_meta = {k: v or "TODO" for k, v in project_meta.items()}
    content_blobs = [
        p.revisions[-1].content if p.revisions else "" for p in project_.pages
    ]
    xml_blob = proofing_utils.to_tei_xml(project_meta, content_blobs)

    response = make_response(xml_blob, 200)
    response.mimetype = "text/xml"
    return response


@bp.route("/<slug>/search")
@login_required
def search(slug):
    """Search across all of the project's pages.

    This is useful for finding typos that repeat across the project.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = SearchForm(request.args)
    if not form.validate():
        return render_template(
            "proofing/projects/search.html", project=project_, form=form
        )

    query = form.query.data
    results = []
    for page_ in project_.pages:
        if not page_.revisions:
            continue

        matches = []

        latest = page_.revisions[-1]
        for line in latest.content.splitlines():
            if query in line:
                matches.append(
                    {
                        "text": escape(line).replace(
                            query, Markup(f"<mark>{escape(query)}</mark>")
                        ),
                    }
                )
        if matches:
            results.append(
                {
                    "slug": page_.slug,
                    "matches": matches,
                }
            )
    return render_template(
        "proofing/projects/search.html",
        project=project_,
        form=form,
        query=query,
        results=results,
    )


@bp.route("/<slug>/batch-ocr", methods=["GET", "POST"])
@login_required
def batch_ocr(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    if request.method == "POST":
        task = ocr_tasks.run_ocr_for_book(
            app_env=current_app.config["AMBUDA_ENVIRONMENT"],
            project=project_,
        )
        if task:
            return render_template(
                "proofing/projects/batch-ocr-post.html",
                project=project_,
                status="PENDING",
                current=0,
                total=0,
                percent=0,
                task_id=task.id,
            )
        else:
            flash("All pages in this project have at least one edit already.")

    return render_template(
        "proofing/projects/batch-ocr.html",
        project=project_,
    )


@bp.route("/batch-ocr-status/<task_id>")
def batch_ocr_status(task_id):
    r = GroupResult.restore(task_id, app=celery_app)
    assert r, task_id

    if r.results:
        current = r.completed_count()
        total = len(r.results)
        percent = current / total

        status = None
        if total:
            if current == total:
                status = "SUCCESS"
            else:
                status == "PROGRESS"
        else:
            status = "FAILURE"

        data = {
            "status": status,
            "current": current,
            "total": total,
            "percent": percent,
        }
    else:
        data = {
            "status": "PENDING",
            "current": 0,
            "total": 0,
            "percent": 0,
        }

    return render_template(
        "include/ocr-progress.html",
        **data,
    )


@bp.route("/<slug>/admin", methods=["GET", "POST"])
@admin_required
def admin(slug):
    """View admin controls for the project.

    We restrict these operations to admins because they are destructive in the
    wrong hands. Current list of admin operations:

    - delete project
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = DeleteProjectForm()
    if form.validate_on_submit():
        if form.slug.data == slug:
            session = q.get_session()
            session.delete(project_)
            session.commit()

            flash(f"Deleted project {slug}")
            return redirect(url_for("proofing.index"))
        else:
            form.slug.errors.append("Mismatch with project slug.")

    return render_template(
        "proofing/projects/admin.html",
        project=project_,
        form=form,
    )
