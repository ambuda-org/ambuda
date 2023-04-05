import logging
import re
from dataclasses import dataclass

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
from wtforms import (
    BooleanField,
    FieldList,
    Form,
    FormField,
    HiddenField,
    StringField,
    SubmitField,
)
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks import app as celery_app
from ambuda.tasks import ocr as ocr_tasks
from ambuda.utils import project_utils, proofing_utils
from ambuda.utils.revisions import add_revision
from ambuda.views.proofing.decorators import moderator_required, p2_required

bp = Blueprint("project", __name__)
LOG = logging.getLogger(__name__)


def _is_valid_page_number_spec(_, field):
    try:
        _ = project_utils.parse_page_number_spec(field.data)
    except Exception as e:
        raise ValidationError("The page number spec isn't valid.") from e


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


class MatchForm(Form):
    selected = BooleanField()
    replace = HiddenField(validators=[DataRequired()])


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


def validate_matches(form, field):
    for match_form in field:
        if match_form.errors:
            raise ValidationError("Invalid match form values.")


class PreviewChangesForm(ReplaceForm):
    class Meta:
        csrf = False

    matches = FieldList(FormField(MatchForm), validators=[validate_matches])
    submit = SubmitField("Save selected changes")


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


@dataclass
class Replacement:
    """Models a replacement of a specific page/line."""

    #: slug of the page that contains this replacement.
    page_slug: str
    #: The 0-indexed line number.
    line_num: int
    #: Regex splits of a line. Odd indices match the query phrase.
    splits: list[str]
    #: The replacement for the odd indices in `splits`.
    replacement: str

    @property
    def form_key(self) -> str:
        return f"match{self.page_slug}-{self.line_num}"

    @property
    def replace_key(self) -> str:
        return self.form_key + "-replace"

    @property
    def name(self) -> str:
        return f"match-{self.page_slug}-{self.line_num}"

    @property
    def marked_query(self) -> str:
        buf = []
        for i, t in enumerate(self.splits):
            if i % 2 == 1:
                buf.append("<mark>")
                buf.append(escape(t))
                buf.append("</mark>")
            else:
                buf.append(escape(t))
        return "".join(buf)

    @property
    def result(self) -> str:
        buf = []
        for i, t in enumerate(self.splits):
            if i % 2 == 1:
                buf.append(self.replacement)
            else:
                buf.append(t)
        return "".join(buf)

    @property
    def marked_replace(self) -> str:
        buf = []
        for i, t in enumerate(self.splits):
            if i % 2 == 1:
                buf.append("<mark>")
                buf.append(escape(self.replacement))
                buf.append("</mark>")
            else:
                buf.append(escape(t))
        return "".join(buf)


def _find_replacements(project_, query: str, replace: str) -> list[Replacement]:
    """Find all possible replacements of `query` with `replace` in `project_`."""

    # Use `re.UNICODE` to support unicode search/replace.
    re_query = re.compile(f"({query})", re.UNICODE)
    results = []
    for page_ in project_.pages:
        if not page_.revisions:
            continue

        latest = page_.revisions[-1]
        for line_num, line in enumerate(latest.content.splitlines()):
            try:
                splits = re_query.split(line)
            except TimeoutError:
                LOG.warning(f"Regex timed out for line: `{line}`")
                continue

            if len(splits) > 1:
                # If length is 1, there are no matches.
                results.append(
                    Replacement(
                        page_slug=page_.slug,
                        line_num=line_num,
                        splits=splits,
                        replacement=replace,
                    )
                )
    return results


@bp.route("/<slug>/replace", methods=["GET"])
@p2_required
def replace(slug):
    """Search and replace a string across all of the project's pages.

    This is useful to replace a string across the project in one shot.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = ReplaceForm(request.args)
    if not form.validate():
        invalid_keys = list(form.errors.keys())
        LOG.debug(f"Invalid form - {request.method}, invalid keys: {invalid_keys}")
        return render_template(
            "proofing/projects/replace.html", project=project_, form=ReplaceForm()
        )

    query = form.query.data
    replace = form.replace.data
    results = _find_replacements(project_, query=query, replace=replace)

    return render_template(
        "proofing/projects/replace.html",
        project=project_,
        form=form,
        submit_changes_form=PreviewChangesForm(),
        query=query,
        replace=replace,
        results=results,
        num_matches=len(results),
    )


@bp.route("/<slug>/replace", methods=["POST"])
@p2_required
def replace_post(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    # FIXME(Kishore): find a way to validate this form. Current `matches` are
    # coming in the way of validators.
    form = PreviewChangesForm(request.form)

    query = form.query.data
    replace = form.replace.data
    all_matches = _find_replacements(project_, query=query, replace=replace)

    selected_keys = {
        key
        for key, value in request.form.items()
        if key.startswith("match")
        and not key.endswith("replace")
        and value == "selected"
    }
    selected_matches = {
        (x.page_slug, x.line_num): x for x in all_matches if x.form_key in selected_keys
    }

    num_replacements = 0
    num_pages_changed = 0
    for page_ in project_.pages:
        if not page_.revisions:
            continue

        buf = []
        latest = page_.revisions[-1]
        for line_num, line in enumerate(latest.content.splitlines()):
            key = (page_.slug, line_num)
            try:
                match = selected_matches[key]
                buf.append(match.result)
                num_replacements += 1
            except KeyError:
                buf.append(line)
                continue

        new_content = "\n".join(buf)
        if new_content != latest.content:
            num_pages_changed += 1
            # Add a new revision to the page
            new_summary = f'Replaced "{query}" with "{replace}"'
            add_revision(
                page=page_,
                summary=new_summary,
                content=new_content,
                status=page_.status.name,
                version=page_.version,
                author_id=current_user.id,
            )

    if num_replacements:
        flash(
            f"Saved {num_replacements} changes across {num_pages_changed} page(s).",
            "success",
        )
    else:
        flash("No changes made.", "warning")
    return redirect(url_for("proofing.project.edit", slug=slug))


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
            form.slug.errors.append("Deletion failed (incorrect field value).")

    return render_template(
        "proofing/projects/admin.html",
        project=project_,
        form=form,
    )
