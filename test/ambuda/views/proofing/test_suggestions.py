"""Tests for the suggestions flow."""

import json

from sqlalchemy import select

import ambuda.database as db
from ambuda.models.proofing import SuggestionStatus
from ambuda.queries import get_session
from ambuda.utils.diff import revision_diff_ops


VALID_CONTENT = "<page>\n<p>suggested content</p>\n</page>"


def _create_suggestion(session, project_id, page_id, revision_id, user_id=None):
    """Helper to create a suggestion directly in the DB."""
    suggestion = db.Suggestion(
        project_id=project_id,
        page_id=page_id,
        revision_id=revision_id,
        user_id=user_id,
        content=VALID_CONTENT,
        explanation="fixed a typo",
    )
    session.add(suggestion)
    session.commit()
    return suggestion


def _get_test_ids(session):
    """Get project_id, page_id, revision_id for test-project/page 1."""
    project = session.scalars(select(db.Project).filter_by(slug="test-project")).one()
    page = session.scalars(
        select(db.Page).filter(
            (db.Page.project_id == project.id) & (db.Page.slug == "1")
        )
    ).one()
    revision = page.revisions[-1]
    return project.id, page.id, revision.id


def _make_stale_revision_id(session):
    """Create a second revision on the test page so the first becomes stale.

    Returns the old (stale) revision_id.
    """
    project = session.scalars(select(db.Project).filter_by(slug="test-project")).one()
    page = session.scalars(
        select(db.Page).filter(
            (db.Page.project_id == project.id) & (db.Page.slug == "1")
        )
    ).one()
    old_revision_id = page.revisions[-1].id
    new_rev = db.Revision(
        project_id=project.id,
        page_id=page.id,
        author_id=page.revisions[-1].author_id,
        status_id=page.revisions[-1].status_id,
        content="Updated content",
    )
    session.add(new_rev)
    session.flush()
    return old_revision_id


def test_suggestions_index__unauth(client):
    r = client.get("/proofing/suggestions/")
    assert r.status_code == 302


def test_suggestions_index__no_p1(no_p1_client):
    r = no_p1_client.get("/proofing/suggestions/")
    assert r.status_code == 302


def test_suggestions_index__p1(rama_client):
    r = rama_client.get("/proofing/suggestions/")
    assert r.status_code == 200
    assert "Suggestions" in r.text


def test_suggestions_index__filter_by_status(rama_client):
    r = rama_client.get("/proofing/suggestions/?status=accepted")
    assert r.status_code == 200

    r = rama_client.get("/proofing/suggestions/?status=rejected")
    assert r.status_code == 200

    # Invalid status falls back to pending
    r = rama_client.get("/proofing/suggestions/?status=foo")
    assert r.status_code == 200


def test_suggestions_index__cursor_pagination(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s1_id, s2_id = s1.id, s2.id

    r = rama_client.get(f"/proofing/suggestions/?before={s2_id}")
    assert r.status_code == 200
    assert f"/suggestions/{s2_id}/review" not in r.text
    assert f"/suggestions/{s1_id}/review" in r.text

    # Invalid cursor is ignored gracefully
    r = rama_client.get("/proofing/suggestions/?before=notanumber")
    assert r.status_code == 200


def test_edit_post__no_p1_creates_suggestion(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        before_count = len(session.scalars(select(db.Suggestion)).all())

    r = no_p1_client.post(
        "/proofing/test-project/1/",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
            "summary": "",
            "explanation": "my explanation",
        },
    )
    assert r.status_code == 200
    assert "Your suggestion has been submitted for review" in r.text

    with flask_app.app_context():
        session = get_session()
        after = session.scalars(select(db.Suggestion)).all()
        assert len(after) == before_count + 1
        newest = after[-1]
        assert newest.explanation == "my explanation"
        assert newest.status == SuggestionStatus.PENDING
        assert newest.user_id is not None


def test_edit_post__anonymous_creates_suggestion(client, flask_app):
    r = client.post(
        "/proofing/test-project/1/",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
            "summary": "",
            "explanation": "",
        },
    )
    assert r.status_code == 200
    assert "Your suggestion has been submitted for review" in r.text

    with flask_app.app_context():
        session = get_session()
        stmt = select(db.Suggestion).order_by(db.Suggestion.id.desc())
        newest = session.scalars(stmt).first()
        assert newest.user_id is None


def test_edit_post__p1_saves_directly(rama_client):
    r = rama_client.post(
        "/proofing/test-project/1/",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
            "summary": "",
        },
    )
    assert r.status_code == 200
    assert '"canSaveDirectly": true' in r.text
    assert "Saved changes" in r.text


def test_accept__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(f"/proofing/suggestions/{suggestion_id}/accept")
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.ACCEPTED


def test_accept__stale_revision(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        stale_id = _make_stale_revision_id(session)
        suggestion = _create_suggestion(
            session, project_id, page_id, revision_id=stale_id
        )
        suggestion_id = suggestion.id

    r = rama_client.post(f"/proofing/suggestions/{suggestion_id}/accept")
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.PENDING


def test_reject__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(f"/proofing/suggestions/{suggestion_id}/reject")
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.REJECTED


def test_accept__nonexistent(rama_client):
    r = rama_client.post("/proofing/suggestions/99999/accept")
    assert r.status_code == 302


def test_reject__nonexistent(rama_client):
    r = rama_client.post("/proofing/suggestions/99999/reject")
    assert r.status_code == 302


def test_accept__unauth(client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = client.post(f"/proofing/suggestions/{suggestion_id}/accept")
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.PENDING


def test_reject__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.post(f"/proofing/suggestions/{suggestion_id}/reject")
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.PENDING


def test_edit_page__p1_sees_save_button(rama_client):
    r = rama_client.get("/proofing/test-project/1/")
    assert "Save" in r.text


def test_edit_page__no_p1_sees_suggest_button(no_p1_client):
    r = no_p1_client.get("/proofing/test-project/1/")
    assert "Suggest" in r.text


def test_edit_page__anonymous_sees_suggest_button(client):
    r = client.get("/proofing/test-project/1/")
    assert "Suggest" in r.text


def test_review__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Changes" in r.text
    assert "Page image" in r.text
    assert "Submit" in r.text
    assert "Reject" in r.text


def test_review__nonexistent(rama_client):
    r = rama_client.get("/proofing/suggestions/99999/review")
    assert r.status_code == 302


def test_review__unauth(client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 302


def test_review__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 302


# --- revision_diff_ops tests ---


def test_revision_diff_ops__equal():
    ops = revision_diff_ops("hello", "hello")
    assert len(ops) == 1
    assert ops[0] == {"op": "equal", "old": "hello", "new": "hello"}


def test_revision_diff_ops__insert():
    ops = revision_diff_ops("ab", "aXb")
    op_types = [o["op"] for o in ops]
    assert "insert" in op_types
    inserted = [o for o in ops if o["op"] == "insert"]
    assert inserted[0]["new"] == "X"
    assert inserted[0]["old"] == ""


def test_revision_diff_ops__delete():
    ops = revision_diff_ops("aXb", "ab")
    op_types = [o["op"] for o in ops]
    assert "delete" in op_types
    deleted = [o for o in ops if o["op"] == "delete"]
    assert deleted[0]["old"] == "X"
    assert deleted[0]["new"] == ""


def test_revision_diff_ops__replace():
    ops = revision_diff_ops("abc", "aZc")
    op_types = [o["op"] for o in ops]
    assert "replace" in op_types
    replaced = [o for o in ops if o["op"] == "replace"]
    assert replaced[0]["old"] == "b"
    assert replaced[0]["new"] == "Z"


def test_revision_diff_ops__reconstruction():
    """Concatenating all 'new' values reproduces the new string."""
    old, new = "hello world", "hello brave new world"
    ops = revision_diff_ops(old, new)
    reconstructed = "".join(o["new"] for o in ops)
    assert reconstructed == new


def test_revision_diff_ops__reconstruction_old():
    """Concatenating all 'old' values reproduces the old string."""
    old, new = "hello world", "hello brave new world"
    ops = revision_diff_ops(old, new)
    reconstructed = "".join(o["old"] for o in ops)
    assert reconstructed == old


# --- submit-review route tests ---


def test_submit_review__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/submit-review",
        data=json.dumps({"content": "custom reviewed content"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.ACCEPTED


def test_submit_review__stale(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        stale_id = _make_stale_revision_id(session)
        suggestion = _create_suggestion(
            session, project_id, page_id, revision_id=stale_id
        )
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/submit-review",
        data=json.dumps({"content": "content"}),
        content_type="application/json",
    )
    assert r.status_code == 409

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.PENDING


def test_submit_review__missing_content(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/submit-review",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_submit_review__nonexistent(rama_client):
    r = rama_client.post(
        "/proofing/suggestions/99999/submit-review",
        data=json.dumps({"content": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 404


def test_submit_review__already_processed(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.ACCEPTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/submit-review",
        data=json.dumps({"content": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_submit_review__unauth(client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = client.post(
        f"/proofing/suggestions/{suggestion_id}/submit-review",
        data=json.dumps({"content": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 302


def test_review__accepted_shows_readonly_diff(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.ACCEPTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Changes" in r.text
    # Read-only: no Submit button, no Alpine suggestionReview component
    assert "Submit" not in r.text
    assert "suggestionReview" not in r.text
    assert "Accepted" in r.text


def test_review__rejected_shows_readonly_diff(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.REJECTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Changes" in r.text
    assert "Submit" not in r.text
    assert "suggestionReview" not in r.text
    assert "Rejected" in r.text
