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


def test_publish_config_save__rename_updates_text_slug(rama_client):
    """Editing a config's slug renames the linked Text in place."""
    session = get_session()
    project_id = session.execute(
        select(db.Project.id).filter_by(slug="test-project")
    ).scalar_one()

    text = db.Text(
        slug="rename-old", title="Old Title", language="sa", stage=TextStage.STUB
    )
    session.add(text)
    session.flush()
    pc = PublishConfig(project_id=project_id, text_id=text.id)
    session.add(pc)
    session.commit()
    pc_id = pc.id
    text_id = text.id

    config_list = [
        {
            "id": pc_id,
            "slug": "rename-new",
            "title": "New Title",
            "language": "sa",
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
        # The original Text row should still exist, with the new slug.
        renamed = session.get(db.Text, text_id)
        assert renamed is not None
        assert renamed.slug == "rename-new"
        assert renamed.title == "New Title"

        # No leftover Text with the old slug.
        old = session.execute(
            select(db.Text).filter_by(slug="rename-old")
        ).scalar_one_or_none()
        assert old is None

        # The PublishConfig still points to the same Text.
        pcs = (
            session.execute(
                select(PublishConfig).where(PublishConfig.project_id == project_id)
            )
            .scalars()
            .all()
        )
        assert any(p.text_id == text_id for p in pcs)
    finally:
        _cleanup_config_and_text("rename-new")
        _cleanup_config_and_text("rename-old")


def test_publish_config_save__rename_conflict_aborts(rama_client, flask_app):
    """Renaming to a slug owned by another text fails without orphaning."""
    session = get_session()
    project_id = session.execute(
        select(db.Project.id).filter_by(slug="test-project")
    ).scalar_one()

    other = db.Text(
        slug="rename-blocker", title="Other", language="sa", stage=TextStage.STUB
    )
    session.add(other)
    text = db.Text(
        slug="rename-source", title="Src", language="sa", stage=TextStage.STUB
    )
    session.add(text)
    session.flush()
    pc = PublishConfig(project_id=project_id, text_id=text.id)
    session.add(pc)
    session.commit()
    pc_id = pc.id

    config_list = [
        {
            "id": pc_id,
            "slug": "rename-blocker",
            "title": "Src",
            "language": "sa",
        },
    ]

    flask_app.config["TESTING"] = False
    try:
        rama_client.post(
            "/proofing/test-project/publish",
            data={"config": json.dumps(config_list)},
        )
    finally:
        flask_app.config["TESTING"] = True

    session = get_session()
    # The source text keeps its old slug, the blocker is untouched.
    assert (
        session.execute(select(db.Text).filter_by(slug="rename-source")).scalar_one()
        is not None
    )
    assert (
        session.execute(select(db.Text).filter_by(slug="rename-blocker")).scalar_one()
        is not None
    )

    _cleanup_config_and_text("rename-source")
    _cleanup_config_and_text("rename-blocker")


def test_publish_config_save__preserves_pc_id_on_update(rama_client):
    """Saving without changes keeps the existing PublishConfig row (no id churn)."""
    session = get_session()
    project_id = session.execute(
        select(db.Project.id).filter_by(slug="test-project")
    ).scalar_one()

    text = db.Text(
        slug="stable-id-text", title="Stable", language="sa", stage=TextStage.STUB
    )
    session.add(text)
    session.flush()
    pc = PublishConfig(project_id=project_id, text_id=text.id, target="(page 1 1)")
    session.add(pc)
    session.commit()
    pc_id = pc.id

    config_list = [
        {
            "id": pc_id,
            "slug": "stable-id-text",
            "title": "Stable",
            "target": "(page 1 1)",
            "language": "sa",
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
        # The PublishConfig row should still have the same id.
        same_pc = session.get(PublishConfig, pc_id)
        assert same_pc is not None
        assert same_pc.target == "(page 1 1)"
    finally:
        _cleanup_config_and_text("stable-id-text")


def test_publish_config_save__remove_entry_deletes_stub_and_config(rama_client):
    """Dropping an entry removes its PublishConfig and its stub text."""
    session = get_session()
    project_id = session.execute(
        select(db.Project.id).filter_by(slug="test-project")
    ).scalar_one()

    keep_text = db.Text(
        slug="keep-text", title="Keep", language="sa", stage=TextStage.STUB
    )
    drop_text = db.Text(
        slug="drop-text", title="Drop", language="sa", stage=TextStage.STUB
    )
    session.add_all([keep_text, drop_text])
    session.flush()
    keep_pc = PublishConfig(project_id=project_id, text_id=keep_text.id)
    drop_pc = PublishConfig(project_id=project_id, text_id=drop_text.id)
    session.add_all([keep_pc, drop_pc])
    session.commit()
    keep_pc_id = keep_pc.id

    config_list = [
        {
            "id": keep_pc_id,
            "slug": "keep-text",
            "title": "Keep",
            "language": "sa",
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
        # Kept text and config still exist.
        assert session.get(PublishConfig, keep_pc_id) is not None
        assert (
            session.execute(
                select(db.Text).filter_by(slug="keep-text")
            ).scalar_one_or_none()
            is not None
        )
        # Dropped text is gone (it was a stub).
        assert (
            session.execute(
                select(db.Text).filter_by(slug="drop-text")
            ).scalar_one_or_none()
            is None
        )
    finally:
        _cleanup_config_and_text("keep-text")
        _cleanup_config_and_text("drop-text")


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
