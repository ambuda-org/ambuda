from dataclasses import dataclass
from typing import Optional

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
from ambuda.utils import project_utils
from ambuda.utils.assets import get_page_image_filepath
from ambuda.utils.diff import revision_diff
from ambuda.utils.revisions import EditException, add_revision
from ambuda.views.api import bp as api
from ambuda.views.site import bp as site

bp = Blueprint("page", __name__)


@dataclass
class PageContext:
    """A page, its project, and some navigation data."""

    #: The current project.
    project: db.Project
    #: The current page.
    cur: db.Page
    #: The previous page.
    prev: Optional[db.Page]
    #: The next page.
    next: Optional[db.Page]


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


def _get_page_context(project_slug: str, page_slug: str) -> Optional[PageContext]:
    """Get the previous, current, and next pages for the given project.

    :param pages: all of the pages in this project.
    :param slug: the slug for the current page.
    """
    project_ = q.project(project_slug)
    if project_ is None:
        return None

    pages = project_.pages
    found = False
    i = 0
    for i, s in enumerate(pages):
        if s.slug == page_slug:
            found = True
            break

    if not found:
        return None

    prev = pages[i - 1] if i > 0 else None
    cur = pages[i]
    next = pages[i + 1] if i < len(pages) - 1 else None
    return PageContext(project=project_, cur=cur, prev=prev, next=next)


def _get_page_title(project_: db.Project, page_: db.Page) -> str:
    if not project_.page_numbers:
        return page_.slug

    page_rules = project_utils.parse_page_number_spec(project_.page_numbers)
    page_titles = project_utils.apply_rules(len(project_.pages), page_rules)
    for title, cur in zip(page_titles, project_.pages):
        if cur.id == page_.id:
            return title

    # We shouldn't reach this case, but if we do, reuse the page's slug.
    return page.slug


@bp.route("/<project_slug>/<page_slug>/", methods=["GET", "POST"])
def edit(project_slug, page_slug):
    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        abort(404)

    cur = ctx.cur
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
    else:
        form.version.data = cur.version

        # FIXME: less hacky approach?
        status_names = {s.id: s.name for s in q.page_statuses()}
        form.status.data = status_names[cur.status_id]

        if cur.revisions:
            latest_revision = cur.revisions[-1]
            form.content.data = latest_revision.content

    is_r0 = cur.status.name == SitePageStatus.R0
    image_title = cur.slug
    page_title = _get_page_title(ctx.project, cur)

    has_edits = bool(cur.revisions)
    is_r0 = cur.status.name == SitePageStatus.R0

    # Keep args in sync with `edit`. (We can't unify these functions easily
    # because one function requires login but the other doesn't. Helper
    # functions don't have any obvious cutting points.
    return render_template(
        "proofing/pages/edit.html",
        form=form,
        project=ctx.project,
        prev=ctx.prev,
        cur=cur,
        next=next,
        next=ctx.next,
        has_edits=True,
        conflict=conflict,
        image_title=image_title,
        page_title=page_title,
        is_r0=is_r0,
    )


@site.route("/static/uploads/<project_slug>/pages/<page_slug>.jpg")
def page_image(project_slug, page_slug):
    # In production, serve this directly via nginx.
    assert current_app.debug
    image_path = get_page_image_filepath(project_slug, page_slug)
    return send_file(image_path)


@bp.route("/<project_slug>/<page_slug>/history")
def history(project_slug, page_slug):
    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        abort(404)

    return render_template(
        "proofing/pages/history.html",
        project=ctx.project,
        cur=ctx.cur,
        prev=ctx.prev,
        next=ctx.next,
    )


@bp.route("/<project_slug>/<page_slug>/revision/<revision_id>")
def revision(project_slug, page_slug, revision_id):
    """View a specific revision for some page."""
    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        abort(404)

    cur = ctx.cur
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
        project=ctx.project,
        cur=cur,
        prev=ctx.prev,
        next=ctx.next,
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
