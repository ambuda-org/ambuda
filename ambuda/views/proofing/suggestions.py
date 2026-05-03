"""Routes for reviewing suggestions from non-P1 users."""

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, select

from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.models.proofing import SuggestionStatus
from ambuda.utils.diff import revision_diff
from ambuda.utils.project_structuring import ProofPage
from ambuda.utils.revisions import EditError, add_revision
from ambuda.utils.xml_validation import validate_proofing_xml
from ambuda.views.proofing.decorators import p1_required
from ambuda.views.proofing.page import _get_page_context, _get_page_data_dict

bp = Blueprint("suggestions", __name__)


PAGE_SIZE = 100
VALID_STATUSES = {s.value for s in SitePageStatus}


def _status_clause(status_filter):
    if status_filter == "pending":
        return db.Suggestion.status == SuggestionStatus.PENDING
    return db.Suggestion.status.in_(
        [SuggestionStatus.ACCEPTED, SuggestionStatus.REJECTED]
    )


def _suggestion_status_filter(suggestion):
    return "pending" if suggestion.status == SuggestionStatus.PENDING else "complete"


def _adjacent_review_url(session, suggestion, direction):
    """Return URL of the next/previous suggestion of the same status family.

    direction: "next" (older id) or "prev" (newer id).
    """
    status_filter = _suggestion_status_filter(suggestion)
    clause = _status_clause(status_filter)
    if direction == "next":
        stmt = (
            select(db.Suggestion)
            .filter(clause, db.Suggestion.id < suggestion.id)
            .order_by(db.Suggestion.id.desc())
            .limit(1)
        )
    else:
        stmt = (
            select(db.Suggestion)
            .filter(clause, db.Suggestion.id > suggestion.id)
            .order_by(db.Suggestion.id.asc())
            .limit(1)
        )
    adj = session.scalars(stmt).first()
    if adj is None:
        return None
    return url_for("proofing.suggestions.review", id=adj.id)


def _diff_base_content(suggestion) -> str:
    """Return the content the suggestion's diff is computed against.

    Prefers the latest revision (so the reviewer sees what *their* save would
    actually change); falls back to the revision the suggestion was made
    against, then to the empty string.
    """
    page = suggestion.page
    latest = page.revisions[-1] if page.revisions else None
    if latest is not None:
        return latest.content
    if suggestion.revision is not None:
        return suggestion.revision.content
    return ""


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
    """List suggestions, filtered by status, with offset pagination."""
    status_filter = request.args.get("status", "pending")
    if status_filter not in ("pending", "complete"):
        status_filter = "pending"

    page = request.args.get("page", 1, type=int) or 1
    if page < 1:
        page = 1

    session = q.get_session()
    clause = _status_clause(status_filter)

    total = session.scalar(select(func.count(db.Suggestion.id)).filter(clause)) or 0
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * PAGE_SIZE

    stmt = (
        select(db.Suggestion)
        .filter(clause)
        .order_by(db.Suggestion.id.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    )
    suggestions = list(session.scalars(stmt).all())

    for s in suggestions:
        page_obj = s.page
        latest_revision = page_obj.revisions[-1] if page_obj.revisions else None
        s._is_stale = latest_revision is None or latest_revision.id != s.revision_id

    return render_template(
        "proofing/suggestions.html",
        suggestions=suggestions,
        status_filter=status_filter,
        SuggestionStatus=SuggestionStatus,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@bp.route("/suggestions/<int:id>/review")
@p1_required
def review(id):
    """Review a suggestion in the proofing editor pre-seeded with its content."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        flash("Suggestion not found.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    if suggestion.status != SuggestionStatus.PENDING:
        flash("This suggestion has already been processed.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    project = suggestion.project
    page = suggestion.page
    ctx = _get_page_context(project.slug, page.slug)
    if ctx is None:
        flash("Page not found.", "error")
        return redirect(url_for("proofing.suggestions.index"))

    latest_revision = page.revisions[-1] if page.revisions else None
    is_stale = latest_revision is None or latest_revision.id != suggestion.revision_id

    page_state = _get_page_data_dict(ctx, project)
    page_state["canSaveDirectly"] = True
    page_state["hasEdits"] = True
    # Seed editor with the suggestion's content (run through ProofPage so block
    # ids & marks normalize the same way as latest-revision content).
    page_state["content"] = ProofPage.from_content_and_page_id(
        suggestion.content, page.id
    ).to_xml_string()
    page_state["saveUrl"] = url_for(
        "proofing.suggestions.save_review", id=suggestion.id
    )
    base_content = _diff_base_content(suggestion)
    page_state["suggestion"] = {
        "id": suggestion.id,
        "submitter": suggestion.user.username if suggestion.user else None,
        "explanation": suggestion.explanation or "",
        "isStale": is_stale,
        "indexUrl": url_for("proofing.suggestions.index"),
        "rejectUrl": url_for("proofing.suggestions.reject_api", id=suggestion.id),
        "diffUrl": url_for("proofing.suggestions.diff", id=suggestion.id),
        "diffHtml": revision_diff(base_content, page_state["content"]),
        "nextReviewUrl": _adjacent_review_url(session, suggestion, "next"),
        "prevReviewUrl": _adjacent_review_url(session, suggestion, "prev"),
    }

    from ambuda.views.proofing.page import EditPageForm

    form = EditPageForm()
    form.version.data = page_state["version"]
    form.status.data = page_state["status"]
    form.content.data = page_state["content"]

    return render_template(
        "proofing/pages/proofer.html",
        conflict=None,
        cur=page,
        form=form,
        page_state=page_state,
        page_context=ctx,
        project=project,
    )


@bp.route("/suggestions/<int:id>/save", methods=["POST"])
@p1_required
def save_review(id):
    """Save a reviewed suggestion's content as a new revision (and accept it).

    Returns JSON with the same shape as the page save API so the proofing
    editor's submit flow can use it without changes.
    """
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        return jsonify({"ok": False, "message": "Suggestion not found."}), 404
    if suggestion.status != SuggestionStatus.PENDING:
        return jsonify(
            {"ok": False, "message": "This suggestion has already been processed."}
        ), 400

    page = suggestion.page
    project = suggestion.project

    content = request.form.get("content", "")
    version = request.form.get("version", "")
    status = request.form.get("status", "")
    summary = (request.form.get("summary", "") or "").strip()

    if not content:
        return jsonify({"ok": False, "message": "Content is required."})

    xml_errors = validate_proofing_xml(content)
    if xml_errors:
        messages = [e.message for e in xml_errors]
        return jsonify({"ok": False, "message": "; ".join(messages)})

    if status not in VALID_STATUSES:
        return jsonify({"ok": False, "message": "Invalid status."})

    if not summary:
        summary = (
            f"Accepted suggestion: {suggestion.explanation}"
            if suggestion.explanation
            else "Accepted suggestion"
        )

    try:
        new_version = add_revision(
            page,
            summary=summary,
            content=content,
            status=status,
            version=int(version),
            author_id=current_user.id,
        )
    except EditError:
        conflict = page.revisions[-1] if page.revisions else None
        return jsonify(
            {
                "ok": False,
                "message": (
                    "Edit conflict — the page changed while you were reviewing."
                ),
                "conflict_content": conflict.content if conflict else "",
                "new_version": page.version,
            }
        )

    suggestion.status = SuggestionStatus.ACCEPTED
    session.add(suggestion)
    session.commit()

    return jsonify(
        {
            "ok": True,
            "message": "Suggestion accepted and revision saved.",
            "new_version": new_version,
            "new_status": status,
            "next_review_url": _next_pending_review_url(session, suggestion.id),
            "index_url": url_for("proofing.suggestions.index"),
        }
    )


@bp.route("/suggestions/<int:id>/diff", methods=["POST"])
@p1_required
def diff(id):
    """Return the rendered diff between the suggestion's base and the supplied content.

    Used by the editor's live diff pane.
    """
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        return jsonify({"ok": False, "message": "Suggestion not found."}), 404

    data = request.get_json(silent=True) or {}
    content = data.get("content", "")
    base = _diff_base_content(suggestion)
    return jsonify({"ok": True, "html": revision_diff(base, content)})


@bp.route("/suggestions/<int:id>/reject", methods=["POST"])
@p1_required
def reject(id):
    """Reject a suggestion (form-POST flow; redirects to the suggestions index)."""
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


@bp.route("/suggestions/<int:id>/reject-api", methods=["POST"])
@p1_required
def reject_api(id):
    """Reject a suggestion via AJAX. Returns JSON with the next review URL."""
    session = q.get_session()
    suggestion = session.get(db.Suggestion, id)
    if not suggestion:
        return jsonify({"ok": False, "message": "Suggestion not found."}), 404
    if suggestion.status != SuggestionStatus.PENDING:
        return jsonify(
            {"ok": False, "message": "This suggestion has already been processed."}
        ), 400

    suggestion.status = SuggestionStatus.REJECTED
    session.add(suggestion)
    session.commit()

    return jsonify(
        {
            "ok": True,
            "message": "Suggestion rejected.",
            "next_review_url": _next_pending_review_url(session, suggestion.id),
            "index_url": url_for("proofing.suggestions.index"),
        }
    )


@bp.route("/suggestions/batch-reject", methods=["POST"])
@p1_required
def batch_reject():
    """Reject many pending suggestions at once. Returns JSON."""
    data = request.get_json(silent=True) or {}
    raw_ids = data.get("ids") or []
    ids = []
    for x in raw_ids:
        try:
            ids.append(int(x))
        except (TypeError, ValueError):
            continue

    if not ids:
        return jsonify({"error": "No suggestion IDs provided."}), 400

    session = q.get_session()
    pending = list(
        session.scalars(
            select(db.Suggestion).filter(
                db.Suggestion.id.in_(ids),
                db.Suggestion.status == SuggestionStatus.PENDING,
            )
        ).all()
    )
    for s in pending:
        s.status = SuggestionStatus.REJECTED
        session.add(s)
    session.commit()

    return jsonify({"ok": True, "rejected": len(pending)})
