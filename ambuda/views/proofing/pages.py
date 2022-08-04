import difflib

from flask import render_template, flash, current_app, send_file, Blueprint
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from markupsafe import escape, Markup
from sqlalchemy import update
from werkzeug.exceptions import abort
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea

from ambuda import database as db, queries as q
from ambuda.utils import google_ocr
from ambuda.views.api import bp as api
from ambuda.views.proofing.utils import _get_image_filesystem_path
from ambuda.views.site import bp as site


bp = Blueprint("pages", __name__)


class EditException(Exception):
    """Raised if a user's attempt to edit a page fails."""

    pass


class EditPageForm(FlaskForm):
    summary = StringField("Summary of changes made")
    version = HiddenField("Page version")
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])
    status = SelectField(
        "Status",
        choices=[
            ("reviewed-0", "Unreviewed"),
            ("reviewed-1", "Proofread once"),
            ("reviewed-2", "Proofread twice"),
            ("skip", "No useful text"),
        ],
    )


def _prev_cur_next(pages: list[db.Page], slug: str) -> tuple[db.Page, db.Page, db.Page]:
    """Get the previous, current, and next pages.

    :param pages: all of the pages in this project.
    :param slug: the slug for the current page.
    """
    found = False
    i = 0
    for i, s in enumerate(pages):
        if s.slug == slug:
            found = True
            break

    if not found:
        raise ValueError(f"Unknown slug {slug}")

    prev = pages[i - 1] if i > 0 else None
    cur = pages[i]
    next = pages[i + 1] if i < len(pages) - 1 else None
    return prev, cur, next


def add_revision(
    page: db.Page, summary: str, content: str, status: str, version: int, author_id: int
) -> int:
    # If this doesn't update any rows, there's an edit conflict.
    # Details: https://gist.github.com/shreevatsa/237bd6592771caadecc68c9515403bc3
    # FIXME: rather than do this on the application side, do an `exists` query
    # FIXME: instead? Not sure if this is a clear win, but worth thinking about.

    # FIXME: Check for `proofreading` user permission before allowing changes
    session = q.get_session()
    status_ids = {s.name: s.id for s in q.page_statuses()}
    new_version = version + 1
    result = session.execute(
        update(db.Page)
        .where((db.Page.id == page.id) & (db.Page.version == version))
        .values(version=new_version, status_id=status_ids[status])
    )
    session.commit()

    num_rows_changed = result.rowcount
    if num_rows_changed == 0:
        raise EditException("Edit conflict")

    # Must be 1 since there's exactly one page with the given page ID.
    # If this fails, the application data is in a weird state.
    assert num_rows_changed == 1

    revision_ = db.Revision(
        project_id=page.project_id,
        page_id=page.id,
        summary=summary,
        content=content,
        author_id=author_id,
        status_id=status_ids[status],
    )
    session.add(revision_)
    session.commit()
    return new_version


def _revision_diff(old: str, new: str) -> str:
    matcher = difflib.SequenceMatcher(a=old, b=new)
    output = []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "equal":
            output.append(escape(matcher.a[a0:a1]))
        elif opcode == "insert":
            output.extend(
                [
                    Markup("<ins>"),
                    escape(matcher.b[b0:b1]),
                    Markup("</ins>"),
                ]
            )
        elif opcode == "delete":
            output.extend(
                [
                    Markup("<del>"),
                    escape(matcher.a[a0:a1]),
                    Markup("</del>"),
                ]
            )
        elif opcode == "replace":
            output.extend(
                [
                    Markup("<del>"),
                    escape(matcher.a[a0:a1]),
                    Markup("</del>"),
                ]
            )
            output.extend(
                [
                    Markup("<ins>"),
                    escape(matcher.b[b0:b1]),
                    Markup("</ins>"),
                ]
            )
        else:
            raise RuntimeError(f"Unexpected opcode {opcode}")
    return "".join(output)


@bp.route("/<project_slug>/<page_slug>/")
def edit(project_slug, page_slug):
    project_ = q.project(project_slug)
    if not project_:
        abort(404)
    try:
        prev, cur, next = _prev_cur_next(project_.pages, page_slug)
    except ValueError:
        abort(404)

    form = EditPageForm()
    form.version.data = cur.version

    # FIXME: less hacky approach?
    status_names = {s.id: s.name for s in q.page_statuses()}
    form.status.data = status_names[cur.status_id]

    if cur.revisions:
        latest_revision = cur.revisions[-1]
        form.content.data = latest_revision.content

    return render_template(
        "proofing/pages/edit.html",
        form=form,
        project=project_,
        prev=prev,
        cur=cur,
        next=next,
    )


@bp.route("/<project_slug>/<page_slug>/", methods=["POST"])
@login_required
def edit_post(project_slug, page_slug):
    assert current_user.is_authenticated

    project_ = q.project(project_slug)
    if not project_:
        abort(404)
    try:
        prev, cur, next = _prev_cur_next(project_.pages, page_slug)
    except ValueError:
        abort(404)

    form = EditPageForm()
    conflict = None

    if form.validate_on_submit():
        try:
            new_version = add_revision(
                cur,
                summary=form.summary.data,
                content=form.content.data,
                status=form.status.data,
                version=int(form.version.data),
                author_id=current_user.id,
            )
            form.version.data = new_version
            flash("Saved changes.", "success")
        except EditException:
            # FIXME: in the future, use a proper edit conflict view.
            flash("Edit conflict. Please incorporate the changes below:")
            conflict = cur.revisions[-1]
            form.version.data = cur.version

    return render_template(
        "proofing/pages/edit.html",
        form=form,
        project=project_,
        prev=prev,
        cur=cur,
        next=next,
        conflict=conflict,
    )


@site.route("/static/uploads/<project_slug>/<page_slug>.jpg")
def page_image(project_slug, page_slug):
    # In production, serve this directly via nginx.
    assert current_app.debug
    image_path = _get_image_filesystem_path(project_slug, page_slug)
    return send_file(image_path)


@bp.route("/<project_slug>/<page_slug>/history")
def history(project_slug, page_slug):
    project_ = q.project(project_slug)
    if not project_:
        abort(404)
    try:
        prev, cur, next = _prev_cur_next(project_.pages, page_slug)
    except ValueError:
        abort(404)

    return render_template(
        "proofing/pages/history.html", project=project_, cur=cur, prev=prev, next=next
    )


@bp.route("/<project_slug>/<page_slug>/revision/<revision_id>")
def revision(project_slug, page_slug, revision_id):
    """View a specific revision for some page."""
    project_ = q.project(project_slug)
    if not project_:
        abort(404)

    try:
        prev, cur, next = _prev_cur_next(project_.pages, page_slug)
    except ValueError:
        abort(404)

    prev_revision = None
    cur_revision = None
    for r in cur.revisions:
        if r.id == int(revision_id):
            cur_revision = r
            break
        else:
            prev_revision = r

    if not cur_revision:
        abort(404)

    if prev_revision:
        diff = _revision_diff(prev_revision.content, cur_revision.content)
    else:
        diff = _revision_diff("", cur_revision.content)

    return render_template(
        "proofing/pages/revision.html",
        project=project_,
        cur=cur,
        prev=prev,
        next=next,
        revision=cur_revision,
        diff=diff,
    )


# FIXME: added trailing slash as a quick hack to support OCR routes on
# frontend, which just concatenate the window URL onto "/api/ocr".
@api.route("/ocr/<project_slug>/<page_slug>/")
@login_required
def ocr(project_slug, page_slug):
    """Apply Google OCR to the given page."""
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)

    page_ = q.page(project_.id, page_slug)
    if not page_:
        abort(404)

    image_path = _get_image_filesystem_path(project_slug, page_slug)
    result = google_ocr.full_text_annotation(image_path)
    return result
