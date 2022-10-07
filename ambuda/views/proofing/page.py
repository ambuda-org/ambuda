from flask import Blueprint, current_app, flash, render_template, send_file
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from werkzeug.exceptions import abort
from wtforms import HiddenField, RadioField, StringField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.utils import google_ocr
from ambuda.utils.assets import get_page_image_filepath
from ambuda.utils.diff import revision_diff
from ambuda.utils.revisions import EditException, add_revision
from ambuda.views.api import bp as api
from ambuda.views.site import bp as site

bp = Blueprint("page", __name__)


class EditPageForm(FlaskForm):
    summary = StringField(_l("Edit summary (optional)"))
    version = HiddenField(_l("Page version"))
    content = StringField(
        _l("Page content"), widget=TextArea(), validators=[DataRequired()]
    )
    status = RadioField(
        _l("Status"),
        choices=[
            (SitePageStatus.R0.value, _l("Needs more work")),
            (SitePageStatus.R1.value, _l("Proofed once")),
            (SitePageStatus.R2.value, _l("Proofed twice")),
            (SitePageStatus.SKIP.value, _l("Not relevant")),
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

    has_edits = bool(cur.revisions)
    if has_edits:
        latest_revision = cur.revisions[-1]
        form.content.data = latest_revision.content

    is_r0 = cur.status.name == SitePageStatus.R0

    return render_template(
        "proofing/pages/edit.html",
        form=form,
        project=project_,
        prev=prev,
        cur=cur,
        next=next,
        has_edits=has_edits,
        is_r0=is_r0,
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

    _ = bool(cur.revisions)
    _ = cur.status.name == SitePageStatus.R0

    # Keep args in sync with `edit`. (We can't unify these functions easily
    # because one function requires login but the other doesn't. Helper
    # functions don't have any obvious cutting points.
    return render_template(
        "proofing/pages/edit.html",
        form=form,
        project=project_,
        prev=prev,
        cur=cur,
        next=next,
        has_edits=True,
        conflict=conflict,
    )


@site.route("/static/uploads/<project_slug>/pages/<page_slug>.jpg")
def page_image(project_slug, page_slug):
    # In production, serve this directly via nginx.
    assert current_app.debug
    image_path = get_page_image_filepath(project_slug, page_slug)
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
        if str(r.id) == revision_id:
            cur_revision = r
            break
        else:
            prev_revision = r

    if not cur_revision:
        abort(404)

    if prev_revision:
        diff = revision_diff(prev_revision.content, cur_revision.content)
    else:
        diff = revision_diff("", cur_revision.content)

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

    image_path = get_page_image_filepath(project_slug, page_slug)
    ocr_response = google_ocr.run(image_path)
    return ocr_response.text_content
