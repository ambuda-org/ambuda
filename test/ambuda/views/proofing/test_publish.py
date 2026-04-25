import json
import pytest

from sqlalchemy import select

import ambuda.database as db
from ambuda.models.proofing import LanguageCode, PublishConfig
from ambuda.models.texts import TextStage
from ambuda.queries import get_session, Query
from ambuda.views.proofing.publish import _validate_slug


@pytest.mark.parametrize(
    "slug",
    [
        "ramayana",
        "a-b-c",
        "text123",
        "vol-1-ch-2",
        "a",
        "1",
    ],
)
def test_validate_slug_valid(slug):
    assert _validate_slug(slug) is None


@pytest.mark.parametrize(
    "slug",
    [
        "",
        "-bad",
        "bad-",
        "has--double",
        "Upper",
        "has space",
        "rāmāyaṇa",
        "has_underscore",
        "has.dot",
        "-",
        "---",
    ],
)
def test_validate_slug_invalid(slug):
    assert _validate_slug(slug) is not None


@pytest.mark.parametrize("code", list(LanguageCode))
def test_valid_language_codes(code):
    assert isinstance(code.label, str)
    assert len(code.label) > 0


def test_publish_config_post__invalid_filter(rama_client):
    config_list = [
        {"slug": "test-text", "title": "Test", "target": "(image 1"},
    ]
    resp = rama_client.post(
        "/proofing/test-project/publish",
        data={"config": json.dumps(config_list)},
    )
    assert resp.status_code == 302


# --- Tests for publish config save/load ---


def _cleanup_config_and_text(slug):
    """Remove any PublishConfig and Text created for the given slug."""
    session = get_session()
    text = session.execute(select(db.Text).filter_by(slug=slug)).scalar_one_or_none()
    if text:
        # Delete configs pointing to this text
        session.execute(
            PublishConfig.__table__.delete().where(PublishConfig.text_id == text.id)
        )
        session.delete(text)
    session.commit()


def test_publish_config_save__creates_stub_text(rama_client):
    """Saving a publish config creates a stub Text and links it."""
    session = get_session()

    coll = db.TextCollection(slug="test-pc-coll", title="Test Collection")
    session.add(coll)
    session.flush()
    coll_id = coll.id

    config_list = [
        {
            "slug": "new-test-text",
            "title": "New Test Text",
            "target": "(page 1 1)",
            "author": "Test Author",
            "language": "sa",
            "parent_slug": "",
            "collection_ids": [coll_id],
        },
    ]

    try:
        resp = rama_client.post(
            "/proofing/test-project/publish",
            data={"config": json.dumps(config_list)},
            follow_redirects=True,
        )
        assert resp.status_code == 200

        session = get_session()
        project = session.execute(
            select(db.Project).filter_by(slug="test-project")
        ).scalar_one()

        # A stub Text should have been created
        text = session.execute(
            select(db.Text).filter_by(slug="new-test-text")
        ).scalar_one_or_none()
        assert text is not None
        assert text.title == "New Test Text"
        assert text.language == "sa"
        assert text.stage == TextStage.STUB

        # PublishConfig should link to the stub
        pc = session.execute(
            select(PublishConfig).where(
                PublishConfig.project_id == project.id,
                PublishConfig.text_id == text.id,
            )
        ).scalar_one_or_none()
        assert pc is not None
        assert pc.target == "(page 1 1)"
    finally:
        _cleanup_config_and_text("new-test-text")
        session = get_session()
        session.execute(
            db.TextCollection.__table__.delete().where(
                db.TextCollection.slug == "test-pc-coll"
            )
        )
        session.commit()


def test_publish_config_save__slug_conflict_with_existing_text(rama_client, flask_app):
    """Cannot save a config with a slug that matches an existing public text."""
    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    config_list = [
        {"slug": "pariksha", "title": "Conflict"},
    ]
    flask_app.config["TESTING"] = False
    try:
        rama_client.post(
            "/proofing/test-project/publish",
            data={"config": json.dumps(config_list)},
        )
    finally:
        flask_app.config["TESTING"] = True

    # No new config should have been saved for the conflict slug
    session = get_session()
    pcs = (
        session.execute(
            select(PublishConfig).where(PublishConfig.project_id == project.id)
        )
        .scalars()
        .all()
    )
    for pc in pcs:
        assert pc.text.slug != "pariksha"


def test_publish_config_get__loads_saved_configs(rama_client):
    """GET the publish page and verify saved configs appear."""
    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    text = db.Text(
        slug="get-test-text", title="Get Test", language="sa", stage=TextStage.STUB
    )
    session.add(text)
    session.flush()

    pc = PublishConfig(
        project_id=project.id,
        text_id=text.id,
    )
    session.add(pc)
    session.commit()

    try:
        resp = rama_client.get("/proofing/test-project/publish")
        assert resp.status_code == 200
        assert b"get-test-text" in resp.data
    finally:
        _cleanup_config_and_text("get-test-text")


def test_q_texts__returns_only_public_texts(flask_app):
    """q.texts() returns only public texts, not stubs."""
    with flask_app.app_context():
        session = get_session()

        stub = db.Text(slug="stub-query-test", title="Stub", stage=TextStage.STUB)
        session.add(stub)
        session.commit()

        try:
            all_texts = Query(session).texts()
            slugs = {t.slug for t in all_texts}
            assert "pariksha" in slugs
            assert "stub-query-test" not in slugs
        finally:
            session.delete(stub)
            session.commit()


def test_q_text__returns_only_public_text(flask_app):
    """q.text(slug) returns public texts but not stubs."""
    with flask_app.app_context():
        session = get_session()

        stub = db.Text(slug="stub-lookup-test", title="Stub", stage=TextStage.STUB)
        session.add(stub)
        session.commit()

        try:
            assert Query(session).text("pariksha") is not None
            assert Query(session).text("stub-lookup-test") is None
        finally:
            session.delete(stub)
            session.commit()


def test_q_text__returns_none_for_missing(flask_app):
    """q.text(slug) returns None for nonexistent slug."""
    with flask_app.app_context():
        session = get_session()
        text = Query(session).text("nonexistent-slug-xyz")
        assert text is None
