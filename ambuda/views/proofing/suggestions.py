"""Routes for reviewing suggestions from non-P1 users."""

import json

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.models.proofing import SuggestionStatus
from ambuda.utils.diff import revision_diff, revision_diff_ops
from ambuda.utils.revisions import add_revision
from ambuda.views.proofing.decorators import p1_required
from ambuda.views.proofing.page import _get_image_url

bp = Blueprint("suggestions", __name__)


PAGE_SIZE = 100
VALID_STATUSES = {s.value for s in SitePageStatus}


def _next_pending_review_url(session, current_id):
    """Return the URL for the next pending suggestion to review, or None."""
    stmt = (
        select(db.Suggestion)
        .filter(
            db.Suggestion.status == SuggestionStatus.PENDING,
            db.Suggestion.id != current_id,
        )
        .order_by(db.Suggestion.id.desc())
        .limit(1)
    )
    nxt = session.scalars(stmt).first()
    if nxt is None:
        return None
    return url_for("proofing.suggestions.review", id=nxt.id)


@bp.route("/suggestions/")
@p1_required
def index():
    """List suggestions, filtered by status, with cursor-based pagination."""
    status_filter = request.args.get("status", "pending")
    if status_filter not in ("pending", "complete"):
        status_filter = "pending"

    cursor = request.args.get("before", type=int)

    session = q.get_session()
    if status_filter == "pending":
        status_clause = db.Suggestion.status == SuggestionStatus.PENDING
    else:
        status_clause = db.Suggestion.status.in_(
            [SuggestionStatus.ACCEPTED, SuggestionStatus.REJECTED]
        )
    stmt = select(db.Suggestion).filter(status_clause).order_by(db.Suggestion.id.desc())
    if cursor is not None:
        stmt = stmt.filter(db.Suggestion.id < cursor)
    stmt = stmt.limit(PAGE_SIZE + 1)

    results = list(session.scalars(stmt).all())
    has_next = len(results) > PAGE_SIZE
    suggestions = results[:PAGE_SIZE]

    next_cursor = suggestions[-1].id if has_next and suggestions else None

    # For each suggestion, compute staleness and diff against the base revision
    for s in suggestions:
        page = s.page
        latest_revision = page.revisions[-1] if page.revisions else None
        s._is_stale = latest_revision is None or latest_revision.id != s.revision_id
        base_content = s.revision.content if s.revision else ""
        s._diff = revision_diff(base_content, s.content)

    return render_template(
        "proofing/suggestions.html",
        suggestions=suggestions,
        status_filter=status_filter,
        SuggestionStatus=SuggestionStatus,
        next_cursor=next_cursor,
    )


@bp.route("/suggestions/<int:id>/review")
@p1_required
def review(id):
    """Review a suggestion side-by-side with the source page image."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        flash("Suggestion not found.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    page = suggestion.page
    project = suggestion.project
    latest_revision = page.revisions[-1] if page.revisions else None
    is_stale = latest_revision is None or latest_revision.id != suggestion.revision_id

    base_content = suggestion.revision.content if suggestion.revision else ""
    is_pending = suggestion.status == SuggestionStatus.PENDING

    if is_pending:
        diff_ops = revision_diff_ops(base_content, suggestion.content)
        diff_ops_json = json.dumps(diff_ops)
        diff = None
    else:
        diff_ops_json = None
        diff = revision_diff(base_content, suggestion.content)

    image_url = _get_image_url(project, page)

    current_status = (
        latest_revision.status.name
        if latest_revision and latest_revision.status
        else SitePageStatus.R0.value
    )

    return render_template(
        "proofing/suggestion-review.html",
        suggestion=suggestion,
        project=project,
        page=page,
        diff=diff,
        diff_ops_json=diff_ops_json,
        is_stale=is_stale,
        image_url=image_url,
        current_status=current_status,
    )


@bp.route("/suggestions/<int:id>/accept", methods=["POST"])
@p1_required
def accept(id):
    """Accept a suggestion, creating a new revision."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        flash("Suggestion not found.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    if suggestion.status != SuggestionStatus.PENDING:
        flash("This suggestion has already been processed.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    page = suggestion.page
    latest_revision = page.revisions[-1] if page.revisions else None

    if latest_revision is None or latest_revision.id != suggestion.revision_id:
        flash(
            "This suggestion is based on an outdated revision. "
            "Please review the page manually before accepting.",
            "error",
        )
        return redirect(url_for("proofing.suggestions.index"))

    from flask_login import current_user

    add_revision(
        page,
        summary=f"Accepted suggestion: {suggestion.explanation}"
        if suggestion.explanation
        else "Accepted suggestion",
        content=suggestion.content,
        status=latest_revision.status.name,
        version=page.version,
        author_id=current_user.id,
    )

    suggestion.status = SuggestionStatus.ACCEPTED
    session.add(suggestion)
    session.commit()

    flash("Suggestion accepted and revision created.", "success")
    return redirect(url_for("proofing.suggestions.index"))


@bp.route("/suggestions/<int:id>/submit-review", methods=["POST"])
@p1_required
def submit_review(id):
    """Submit a reviewed suggestion with optionally modified content."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        return jsonify({"error": "Suggestion not found."}), 404

    if suggestion.status != SuggestionStatus.PENDING:
        return jsonify({"error": "This suggestion has already been processed."}), 400

    page = suggestion.page
    latest_revision = page.revisions[-1] if page.revisions else None

    if latest_revision is None or latest_revision.id != suggestion.revision_id:
        return jsonify(
            {"error": "This suggestion is based on an outdated revision."}
        ), 409

    data = request.get_json(silent=True)
    if not data or "content" not in data:
        return jsonify({"error": "Missing content."}), 400

    content = data["content"]

    status = data.get("status") or latest_revision.status.name
    if status not in VALID_STATUSES:
        return jsonify({"error": "Invalid status."}), 400

    summary = (data.get("summary") or "").strip()
    if not summary:
        summary = (
            f"Accepted suggestion: {suggestion.explanation}"
            if suggestion.explanation
            else "Accepted suggestion"
        )

    from flask_login import current_user

    add_revision(
        page,
        summary=summary,
        content=content,
        status=status,
        version=page.version,
        author_id=current_user.id,
    )

    suggestion.status = SuggestionStatus.ACCEPTED
    session.add(suggestion)
    session.commit()

    return jsonify(
        {
            "ok": True,
            "redirect": url_for("proofing.suggestions.index"),
            "next_review_url": _next_pending_review_url(session, suggestion.id),
        }
    )


@bp.route("/suggestions/<int:id>/reject", methods=["POST"])
@p1_required
def reject(id):
    """Reject a suggestion."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        flash("Suggestion not found.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    if suggestion.status != SuggestionStatus.PENDING:
        flash("This suggestion has already been processed.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    suggestion.status = SuggestionStatus.REJECTED
    session.add(suggestion)
    session.commit()

    flash("Suggestion rejected.", "success")
    return redirect(url_for("proofing.suggestions.index"))
