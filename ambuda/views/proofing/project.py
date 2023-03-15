import logging

from celery.result import GroupResult
from flask import (
    Blueprint,
    current_app,
    flash,
    make_response,
    render_template,
    request,
    url_for,
)
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from markupsafe import Markup, escape
from sqlalchemy import orm
from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from wtforms import HiddenField, StringField, SubmitField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks import app as celery_app
from ambuda.tasks import ocr as ocr_tasks
from ambuda.utils import project_utils, proofing_utils
from ambuda.utils.revisions import EditException, add_revision
from ambuda.views.proofing.decorators import moderator_required, p2_required

bp = Blueprint("project", __name__)
LOG = logging.getLogger(__name__)

def _is_valid_page_number_spec(_, field):
    try:
        _ = project_utils.parse_page_number_spec(field.data)
    except Exception:
        raise ValidationError("The page number spec isn't valid.")


class EditMetadataForm(FlaskForm):
    description = StringField(
        _l("Description (optional)"),
        widget=TextArea(),
        render_kw={
            "placeholder": _l(
                "What is this book about? Why is this project interesting?"
            ),
        },
    )
    page_numbers = StringField(
        _l("Page numbers (optional)"),
        widget=TextArea(),
        validators=[_is_valid_page_number_spec],
        render_kw={
            "placeholder": "Coming soon.",
        },
    )
    title = StringField(_l("Title"), validators=[DataRequired()])
    author = StringField(
        _l("Author"),
        render_kw={
            "placeholder": _l("The author of the original work, e.g. Kalidasa."),
        },
    )
    editor = StringField(
        _l("Editor"),
        render_kw={
            "placeholder": _l(
                "The person or organization that created this edition of the text."
            ),
        },
    )
    publisher = StringField(
        _l("Publisher"),
        render_kw={
            "placeholder": _l(
                "The original publisher of this book, e.g. Nirnayasagar."
            ),
        },
    )
    publication_year = StringField(
        _l("Publication year"),
        render_kw={
            "placeholder": _l("The year in which this specific edition was published."),
        },
    )


class SearchForm(FlaskForm):
    class Meta:
        csrf = False

    query = StringField(_l("Query"), validators=[DataRequired()])


class DeleteProjectForm(FlaskForm):
    slug = StringField("Slug", validators=[DataRequired()])


class ReplaceForm(SearchForm):
    class Meta:
        csrf = False

    replace = StringField(_l("Replace"), validators=[DataRequired()])

class SubmitChangesForm(ReplaceForm):
    class Meta:
        csrf = False

    submit = SubmitField("Submit Changes")

class ConfirmReplaceForm(ReplaceForm):
    class Meta:
        csrf = False

    changes = HiddenField("Changes", validators=[DataRequired()])
    confirm = SubmitField("Confirm")
    cancel = SubmitField("Cancel")


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

        flash(_l("Saved changes."), "success")
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

def _replace_text(project_, replace_form: ReplaceForm, query: str, replace: str):
    """
    Gather all matches for the "query" string and pair them the "replace" string.
    """

    results = []

    LOG.info(f'Search/Replace text with {query} and {replace}')
    for page_ in project_.pages:
        if not page_.revisions:
            continue
        matches = []
        latest = page_.revisions[-1]
        for line in latest.content.splitlines():
            LOG.info(f'Search/Replace > {page_.slug}: {line}')
            if query in line:
                LOG.info(f'Search/Replace > appending search/replace {line}') 
                matches.append(
                    {
                        "query": escape(line).replace(
                            query, Markup(f"<mark>{escape(query)}</mark>")
                        ),
                        "replace": escape(line).replace(
                            query, Markup(f"<mark>{escape(replace)}</mark>")
                            ),
                        "checked": False
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
        "proofing/projects/replace.html",
        project=project_,
        form=replace_form,
        submit_changes_form=SubmitChangesForm(),
        query=query,
        replace=replace,
        results=results,
        )


@bp.route("/<slug>/replace", methods=["GET", "POST"])
@login_required
def replace(slug):
    """Search and replace a string across all of the project's pages.

    This is useful to replace a string across the project in one shot.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = ReplaceForm(request.form)
    if not form.validate():
        invalid_keys = list(form.errors.keys())
        LOG.info(f'Invalid form - {request.method}, invalid keys: {invalid_keys}')
        return render_template(
            "proofing/projects/replace.html", project=project_, form=ReplaceForm()
        )

    # search for "query" string and replace with "update" string
    query = form.query.data
    replace = form.replace.data
    render = _replace_text(project_, replace_form=form, query=query, replace=replace)
    return render


def _select_changes(project_, submit_changes_form: SubmitChangesForm, query: str, replace: str):
    """
    Mark  "query" strings 
    """
    results = []
    LOG.info(f'{__name__}: Mark changes with {query} and {replace}')
    for page_ in project_.pages:
        if not page_.revisions:
            continue

        latest = page_.revisions[-1]
        matches = []
        for line_num, line in enumerate(latest.content.splitlines()):
            form_key = f"match{page_.slug}-{line_num}"
            if getattr(submit_changes_form, form_key, None) and getattr(submit_changes_form, form_key).data:
                matches.append({
                    'query': line,
                    'replace': line.replace(query, replace),
                })

        results.append({
            'page': page_,
            'matches': matches
        })

    selected_count = sum(getattr(submit_changes_form, form_key).data == True for form_key in submit_changes_form._fields)
    LOG.info(f'{__name__} > Number of selected changes = {selected_count}')

    return render_template("proofing/projects/confirm_replace.html",
                           project=project_, form=ConfirmReplaceForm(), query=query, replace=replace, results=results)


# def _mark_changes(project_, form: ReplaceForm, submit_changes_form: SubmitChangesForm, 
#                     query: str, replace: str):
#     """
#     Search for all "query" string
#     """
#     results = []
#     LOG.info(f'Mark changes with {query} and {replace}')
#     for page_ in project_.pages:
#         if not page_.revisions:
#             continue

#         latest = page_.revisions[-1]
#         if submit_changes_form.get("check-all"):
#             # check all matches
#             LOG.info(f'Mark changes > {page_.slug}')
#             for line_num, line in enumerate(latest.content.splitlines()):
                
#                 form_key = f"match{page_.slug}-{line_num}"
#                 submit_changes_form[form_key].data = True
#                 LOG.info(f'Mark changes > Check-all > {form_key}')
#         else:
#             # handle individual match
#             for i, line in enumerate(latest.content.splitlines()):
#                 form_key = f"match{page_.slug}-{line_num}"
#                 if submit_changes_form.get(form_key):
#                     submit_changes_form[form_key].data = True
#                 else:
#                     submit_changes_form[form_key].data = False
#             selected_count = sum(submit_changes_form[form_key].data == True for form_key in submit_changes_form)
#             LOG.info(f'{__name__} > Number of selected changes = {selected_count}')
    
    
#     return render_template("proofing/projects/confirm_replace.html", 
#                     project=project_, form=form, submit_changes_form=submit_changes_form, query=query, replace=replace, results=results)


@bp.route("/<slug>/submit_changes", methods=["GET", "POST"])
@login_required
def submit_changes(slug):
    """Submit selected changes across all of the project's pages.

    This is useful to replace a string across the project in one shot.
    """

    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = SubmitChangesForm(request.form)
    if not form.validate():
        # elif request.form.get("form_submitted") is None:
        invalid_keys = list(form.errors.keys())
        LOG.info(f'{__name__}: Invalid form values - {request.method}, invalid keys: {invalid_keys}')
        return redirect(url_for("proofing.project.replace", slug=slug))

    results = []
    render = None
    # search for "query" string and replace with "update" string
    query = form.query.data
    replace = form.replace.data
    
    LOG.info(f'{__name__}: ({request.method})>  Got to submit method with {query}->{replace} ')
    LOG.info(f'{__name__}: {request.method} > {list(request.form.keys())}')
    
    render = _select_changes(project_, submit_changes_form=form, query=query, replace=replace)
    
    return render


@bp.route("/<slug>/confirm_replace", methods=["GET", "POST"])
@login_required
def confirm_replace(slug):
    """Confirm changes to replace a string across all of the project's pages."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = ConfirmReplaceForm(request.form)
    if not form.validate():
        flash("Invalid input.", "danger")
        invalid_keys = list(form.errors.keys())
        LOG.info(f'{__name__}: Invalid form - {request.method}, invalid keys: {invalid_keys}')
        return redirect(url_for("proofing.project.replace", slug=slug))

    if form.confirm.data:
        query = form.query.data
        replace = form.replace.data
        changes = []

        # Get the changes from the form and store them in a list
        for key, value in request.form.items():
            if key.startswith("match"):
                parts = key.split("-")
                page_slug = parts[1]
                line_num = int(parts[2])
                if parts[3] == "replace":
                    changes.append((page_slug, line_num, value))

        # Apply the changes to each page
        for page in project_.pages:
            lines = page.content.splitlines()
            page_changed = False
            for line_num, line in enumerate(lines):
                for change in changes:
                    change_page_slug, change_line_num, change_replace_value = change
                    if page.slug == change_page_slug and line_num == change_line_num:
                        lines[line_num] = line.replace(query, change_replace_value)
                        page_changed = True
                        break
                if page_changed:
                    break

            # Add a new revision if the page was changed
            if page_changed:
                new_content = "\n".join(lines)
                new_summary = f'Replaced "{query}" with "{replace}" on page {page.slug}'
                new_revision = add_revision(page, new_summary, new_content)
                page.revisions.append(new_revision)

        flash("Changes applied.", "success")
        return redirect(url_for("proofing.projects.replace", slug=slug))

    return render_template("proofing/projects/confirm_replace.html", project=project_, form=form)


@bp.route("/<slug>/batch-ocr", methods=["GET", "POST"])
@p2_required
def batch_ocr(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    if request.method == "POST":
        task = ocr_tasks.run_ocr_for_project(
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
            flash(_l("All pages in this project have at least one edit already."))

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
                status = "PROGRESS"
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
@moderator_required
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
