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


# --- index ---


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


def test_suggestions_index__pagination(rama_client, flask_app, monkeypatch):
    """With PAGE_SIZE=1, page=1 shows the newest, page=2 shows the next."""
    from ambuda.views.proofing import suggestions as s_module

    monkeypatch.setattr(s_module, "PAGE_SIZE", 1)

    with flask_app.app_context():
        session = get_session()
        for s in session.scalars(
            select(db.Suggestion).filter(
                db.Suggestion.status == SuggestionStatus.PENDING
            )
        ).all():
            s.status = SuggestionStatus.REJECTED
        session.commit()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s1_id, s2_id = s1.id, s2.id

    r = rama_client.get("/proofing/suggestions/?status=pending&page=1")
    assert r.status_code == 200
    assert f"/suggestions/{s2_id}/review" in r.text
    assert f"/suggestions/{s1_id}/review" not in r.text

    r = rama_client.get("/proofing/suggestions/?status=pending&page=2")
    assert r.status_code == 200
    assert f"/suggestions/{s1_id}/review" in r.text
    assert f"/suggestions/{s2_id}/review" not in r.text

    # Out-of-range pages clamp to last page rather than 404.
    r = rama_client.get("/proofing/suggestions/?status=pending&page=99")
    assert r.status_code == 200

    # Invalid page value is ignored gracefully.
    r = rama_client.get("/proofing/suggestions/?page=notanumber")
    assert r.status_code == 200


# --- suggestions are created when non-P1 users edit ---


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


def test_page_save_api__anonymous_creates_suggestion(client, flask_app):
    """The AJAX save endpoint accepts anonymous suggestions, mirroring the form flow."""
    with flask_app.app_context():
        session = get_session()
        before_count = len(session.scalars(select(db.Suggestion)).all())

    r = client.post(
        "/api/proofing/test-project/1/save",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
            "summary": "",
            "explanation": "anon test",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "submitted for review" in data["message"]

    with flask_app.app_context():
        session = get_session()
        after = session.scalars(select(db.Suggestion)).all()
        assert len(after) == before_count + 1
        newest = after[-1]
        assert newest.user_id is None
        assert newest.explanation == "anon test"


def test_page_save_api__no_p1_creates_suggestion(no_p1_client, flask_app):
    """Authenticated non-P1 users also create suggestions via the AJAX endpoint."""
    with flask_app.app_context():
        session = get_session()
        before_count = len(session.scalars(select(db.Suggestion)).all())

    r = no_p1_client.post(
        "/api/proofing/test-project/1/save",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
            "summary": "",
            "explanation": "non-p1 test",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True

    with flask_app.app_context():
        session = get_session()
        after = session.scalars(select(db.Suggestion)).all()
        assert len(after) == before_count + 1
        assert after[-1].user_id is not None


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


def test_edit_page__p1_sees_save_button(rama_client):
    r = rama_client.get("/proofing/test-project/1/")
    assert "Save" in r.text


def test_edit_page__no_p1_sees_suggest_button(no_p1_client):
    r = no_p1_client.get("/proofing/test-project/1/")
    assert "Suggest" in r.text


def test_edit_page__anonymous_sees_suggest_button(client):
    r = client.get("/proofing/test-project/1/")
    assert "Suggest" in r.text


# --- review (renders the page editor with a suggestion banner) ---


def test_review__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(
            session, project_id, page_id, revision_id, user_id=1
        )
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    # Renders the proofer template (key id from proofer.html).
    assert 'id="prosemirror-editor"' in r.text
    # Suggestion banner is present.
    assert "Reviewing suggestion by" in r.text
    assert "Reject" in r.text
    # Save URL is wired to the suggestion endpoint, not the regular page save.
    assert f"/proofing/suggestions/{suggestion_id}/save" in r.text


def test_review__anonymous_submitter_banner(rama_client, flask_app):
    """When the suggestion has no user, the banner reads 'anonymous'."""
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Reviewing anonymous suggestion" in r.text


def test_review__nonexistent(rama_client):
    r = rama_client.get("/proofing/suggestions/99999/review")
    assert r.status_code == 302


def test_review__accepted_redirects_to_index(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.ACCEPTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 302
    assert "/proofing/suggestions/" in r.headers["Location"]


def test_review__rejected_redirects_to_index(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.REJECTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
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


def test_review__shows_stale_warning(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        stale_id = _make_stale_revision_id(session)
        suggestion = _create_suggestion(
            session, project_id, page_id, revision_id=stale_id
        )
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Stale" in r.text


def test_review__prev_next_navigation_among_pending(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s3 = _create_suggestion(session, project_id, page_id, revision_id)
        s1_id, s2_id, s3_id = s1.id, s2.id, s3.id

    r = rama_client.get(f"/proofing/suggestions/{s2_id}/review")
    assert r.status_code == 200
    assert f"/proofing/suggestions/{s1_id}/review" in r.text
    assert f"/proofing/suggestions/{s3_id}/review" in r.text


# --- save_review (accept-and-save endpoint) ---


def test_save_review__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id
        page_version_before = session.get(db.Page, page_id).version

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={
            "content": VALID_CONTENT,
            "version": str(page_version_before),
            "status": "reviewed-1",
            "summary": "tidied up",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["new_status"] == "reviewed-1"
    assert data["new_version"] == page_version_before + 1

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.ACCEPTED
        page = session.get(db.Page, s.page_id)
        latest = page.revisions[-1]
        assert latest.summary == "tidied up"
        assert latest.status.name == "reviewed-1"


def test_save_review__default_summary(rama_client, flask_app):
    """When no summary is supplied, falls back to a derived one."""
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id
        page_version_before = session.get(db.Page, page_id).version

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={
            "content": VALID_CONTENT,
            "version": str(page_version_before),
            "status": "reviewed-0",
            "summary": "",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is True

    with flask_app.app_context():
        session = get_session()
        page = session.get(db.Page, page_id)
        latest = page.revisions[-1]
        assert "Accepted suggestion" in latest.summary


def test_save_review__missing_content(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={"content": "", "version": "0", "status": "reviewed-0"},
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is False


def test_save_review__invalid_status(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id
        page_version_before = session.get(db.Page, page_id).version

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={
            "content": VALID_CONTENT,
            "version": str(page_version_before),
            "status": "bogus",
        },
    )
    assert r.status_code == 200
    assert r.get_json()["ok"] is False


def test_save_review__nonexistent(rama_client):
    r = rama_client.post(
        "/proofing/suggestions/99999/save",
        data={"content": VALID_CONTENT, "version": "0", "status": "reviewed-0"},
    )
    assert r.status_code == 404


def test_save_review__already_processed(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.ACCEPTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={"content": VALID_CONTENT, "version": "0", "status": "reviewed-0"},
    )
    assert r.status_code == 400


def test_save_review__edit_conflict(rama_client, flask_app):
    """Saving against a stale page version surfaces a conflict."""
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        stale_id = _make_stale_revision_id(session)
        suggestion = _create_suggestion(
            session, project_id, page_id, revision_id=stale_id
        )
        suggestion_id = suggestion.id

    # Use a version that is older than the page's actual current version.
    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={
            "content": VALID_CONTENT,
            "version": "0",
            "status": "reviewed-0",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is False
    assert "conflict_content" in data

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.PENDING


def test_save_review__unauth(client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={"content": VALID_CONTENT, "version": "0", "status": "reviewed-0"},
    )
    assert r.status_code == 302


def test_save_review__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.post(
        f"/proofing/suggestions/{suggestion_id}/save",
        data={"content": VALID_CONTENT, "version": "0", "status": "reviewed-0"},
    )
    assert r.status_code == 302


def test_save_review__returns_next_review_url(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s1_id, s2_id = s1.id, s2.id
        page_version_before = session.get(db.Page, page_id).version

    r = rama_client.post(
        f"/proofing/suggestions/{s2_id}/save",
        data={
            "content": VALID_CONTENT,
            "version": str(page_version_before),
            "status": "reviewed-0",
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["next_review_url"] == f"/proofing/suggestions/{s1_id}/review"


# --- diff ---


def test_diff__success(rama_client, flask_app):
    """Returns the rendered diff between the suggestion's base and the supplied content."""
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(
        f"/proofing/suggestions/{suggestion_id}/diff",
        data=json.dumps({"content": "<page>\n<p>changed text</p>\n</page>"}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert "<ins>" in data["html"] or "<del>" in data["html"]


def test_diff__nonexistent(rama_client):
    r = rama_client.post(
        "/proofing/suggestions/99999/diff",
        data=json.dumps({"content": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 404


def test_diff__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.post(
        f"/proofing/suggestions/{suggestion_id}/diff",
        data=json.dumps({"content": "x"}),
        content_type="application/json",
    )
    assert r.status_code == 302


def test_review__embeds_initial_diff(rama_client, flask_app):
    """The review page seeds the diff pane with server-rendered HTML."""
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = db.Suggestion(
            project_id=project_id,
            page_id=page_id,
            revision_id=revision_id,
            content="<page>\n<p>completely different</p>\n</page>",
            explanation="big change",
        )
        session.add(suggestion)
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.get(f"/proofing/suggestions/{suggestion_id}/review")
    assert r.status_code == 200
    assert "Changes (vs. current page)" in r.text
    # Initial diff HTML lives inside the page_state JSON.
    assert "diffHtml" in r.text


# --- reject ---


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


def test_reject__nonexistent(rama_client):
    r = rama_client.post("/proofing/suggestions/99999/reject")
    assert r.status_code == 302


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


# --- reject_api (AJAX endpoint used by the editor banner) ---


def test_reject_api__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = rama_client.post(f"/proofing/suggestions/{suggestion_id}/reject-api")
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True

    with flask_app.app_context():
        session = get_session()
        s = session.get(db.Suggestion, suggestion_id)
        assert s.status == SuggestionStatus.REJECTED


def test_reject_api__already_processed(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion.status = SuggestionStatus.ACCEPTED
        session.commit()
        suggestion_id = suggestion.id

    r = rama_client.post(f"/proofing/suggestions/{suggestion_id}/reject-api")
    assert r.status_code == 400


def test_reject_api__nonexistent(rama_client):
    r = rama_client.post("/proofing/suggestions/99999/reject-api")
    assert r.status_code == 404


def test_reject_api__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.post(f"/proofing/suggestions/{suggestion_id}/reject-api")
    assert r.status_code == 302


# --- batch reject ---


def test_batch_reject__success(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s1_id, s2_id = s1.id, s2.id

    r = rama_client.post(
        "/proofing/suggestions/batch-reject",
        data=json.dumps({"ids": [s1_id, s2_id]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["ok"] is True
    assert data["rejected"] == 2

    with flask_app.app_context():
        session = get_session()
        assert session.get(db.Suggestion, s1_id).status == SuggestionStatus.REJECTED
        assert session.get(db.Suggestion, s2_id).status == SuggestionStatus.REJECTED


def test_batch_reject__skips_already_processed(rama_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        s1 = _create_suggestion(session, project_id, page_id, revision_id)
        s2 = _create_suggestion(session, project_id, page_id, revision_id)
        s2.status = SuggestionStatus.ACCEPTED
        session.commit()
        s1_id, s2_id = s1.id, s2.id

    r = rama_client.post(
        "/proofing/suggestions/batch-reject",
        data=json.dumps({"ids": [s1_id, s2_id]}),
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.get_json()["rejected"] == 1

    with flask_app.app_context():
        session = get_session()
        assert session.get(db.Suggestion, s1_id).status == SuggestionStatus.REJECTED
        assert session.get(db.Suggestion, s2_id).status == SuggestionStatus.ACCEPTED


def test_batch_reject__empty_ids(rama_client):
    r = rama_client.post(
        "/proofing/suggestions/batch-reject",
        data=json.dumps({"ids": []}),
        content_type="application/json",
    )
    assert r.status_code == 400


def test_batch_reject__no_p1(no_p1_client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = no_p1_client.post(
        "/proofing/suggestions/batch-reject",
        data=json.dumps({"ids": [suggestion_id]}),
        content_type="application/json",
    )
    assert r.status_code == 302

    with flask_app.app_context():
        session = get_session()
        assert (
            session.get(db.Suggestion, suggestion_id).status == SuggestionStatus.PENDING
        )


def test_batch_reject__unauth(client, flask_app):
    with flask_app.app_context():
        session = get_session()
        project_id, page_id, revision_id = _get_test_ids(session)
        suggestion = _create_suggestion(session, project_id, page_id, revision_id)
        suggestion_id = suggestion.id

    r = client.post(
        "/proofing/suggestions/batch-reject",
        data=json.dumps({"ids": [suggestion_id]}),
        content_type="application/json",
    )
    assert r.status_code == 302


# --- revision_diff_ops utility tests ---


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
