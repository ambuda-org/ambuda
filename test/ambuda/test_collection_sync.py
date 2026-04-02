"""Tests for collection management on Texts.

Covers:
- Publish sync: text.collections set during config save
- Batch edit: text.collections updated directly
- CASCADE deletes on association tables
"""

import pytest

import ambuda.database as db
from ambuda.queries import get_session


@pytest.fixture()
def sync_env(flask_app):
    """Create collections, a text, and a PublishConfig linked to the test project."""
    with flask_app.app_context():
        session = get_session()

        # Collections
        coll_a = db.TextCollection(slug="sync-a", title="Sync A", order=1)
        coll_b = db.TextCollection(slug="sync-b", title="Sync B", order=2)
        session.add_all([coll_a, coll_b])
        session.flush()

        # Use existing project (from conftest)
        project = session.query(db.Project).filter_by(slug="test-project").one()

        # A text for sync testing
        text = db.Text(slug="sync-test-text", title="Sync Test", stage="public")
        session.add(text)
        session.flush()

        # PublishConfig linked to project and text
        pc = db.PublishConfig(
            project_id=project.id,
            text_id=text.id,
            order=0,
        )
        session.add(pc)
        session.commit()

        env = {
            "coll_a_id": coll_a.id,
            "coll_b_id": coll_b.id,
            "text_id": text.id,
            "pc_id": pc.id,
            "project_id": project.id,
        }
        yield env

        # Cleanup
        session.query(db.PublishConfig).filter_by(id=env["pc_id"]).delete()
        text_obj = session.get(db.Text, env["text_id"])
        if text_obj:
            session.query(db.TextSection).filter_by(text_id=text_obj.id).delete()
            text_obj.collections = []
            session.delete(text_obj)
        for cid in [env["coll_a_id"], env["coll_b_id"]]:
            c = session.get(db.TextCollection, cid)
            if c:
                session.delete(c)
        session.commit()


class TestTextCollections:
    """Test setting collections directly on Text."""

    def test_set_collections_on_text(self, flask_app, sync_env):
        with flask_app.app_context():
            session = get_session()
            text = session.get(db.Text, sync_env["text_id"])
            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])
            coll_b = session.get(db.TextCollection, sync_env["coll_b_id"])

            text.collections = [coll_a, coll_b]
            session.commit()

            text = session.get(db.Text, sync_env["text_id"])
            coll_ids = {c.id for c in text.collections}
            assert coll_ids == {sync_env["coll_a_id"], sync_env["coll_b_id"]}

            # Cleanup
            text.collections = []
            session.commit()

    def test_clear_collections_on_text(self, flask_app, sync_env):
        with flask_app.app_context():
            session = get_session()
            text = session.get(db.Text, sync_env["text_id"])
            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])

            text.collections = [coll_a]
            session.commit()

            text.collections = []
            session.commit()

            text = session.get(db.Text, sync_env["text_id"])
            assert text.collections == []


class TestBatchEdit:
    """Test batch edit operations on text.collections."""

    def test_batch_add_collection(self, flask_app, sync_env):
        with flask_app.app_context():
            session = get_session()
            text = session.get(db.Text, sync_env["text_id"])
            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])

            if coll_a not in text.collections:
                text.collections.append(coll_a)
            session.commit()

            text = session.get(db.Text, sync_env["text_id"])
            assert {c.id for c in text.collections} == {sync_env["coll_a_id"]}

            # Cleanup
            text.collections = []
            session.commit()

    def test_batch_remove_collection(self, flask_app, sync_env):
        with flask_app.app_context():
            session = get_session()
            text = session.get(db.Text, sync_env["text_id"])
            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])
            coll_b = session.get(db.TextCollection, sync_env["coll_b_id"])

            text.collections = [coll_a, coll_b]
            session.commit()

            text.collections.remove(coll_b)
            session.commit()

            text = session.get(db.Text, sync_env["text_id"])
            assert {c.id for c in text.collections} == {sync_env["coll_a_id"]}

            # Cleanup
            text.collections = []
            session.commit()

    def test_batch_edit_no_config(self, flask_app, sync_env):
        """If a text has no PublishConfig, batch edit should not error."""
        with flask_app.app_context():
            session = get_session()

            orphan = db.Text(slug="orphan-text", title="Orphan", stage="public")
            session.add(orphan)
            session.flush()

            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])
            orphan.collections.append(coll_a)
            session.commit()

            assert {c.id for c in orphan.collections} == {sync_env["coll_a_id"]}

            # Cleanup
            orphan.collections = []
            session.delete(orphan)
            session.commit()


class TestCascadeDeletes:
    """Test that deleting a collection cascades to association tables."""

    def test_delete_collection_cascades_text_association(self, flask_app, sync_env):
        with flask_app.app_context():
            session = get_session()
            text = session.get(db.Text, sync_env["text_id"])
            coll_a = session.get(db.TextCollection, sync_env["coll_a_id"])

            text.collections = [coll_a]
            session.commit()

            session.delete(coll_a)
            session.commit()

            text = session.get(db.Text, sync_env["text_id"])
            assert sync_env["coll_a_id"] not in {c.id for c in text.collections}

            # Recreate for cleanup fixture
            new_coll = db.TextCollection(
                id=sync_env["coll_a_id"], slug="sync-a", title="Sync A", order=1
            )
            session.add(new_coll)
            session.commit()
