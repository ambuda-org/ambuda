import io
import json
from datetime import datetime

import pytest
from sqlalchemy import select

import ambuda.database as db
from ambuda.queries import get_session
from ambuda.views.admin.tasks import serialize, CollectionExportData


# Sentinel value
class Any:
    pass


def _assert_matches(actual, expected, path: list = None):
    """Recursive comparison on json data.

    NOTE: unused for now, will use soon.
    """
    path = path or []

    if expected is Any:
        pass
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), path
        assert actual.keys() == expected.keys(), path
        for key in actual:
            _assert_matches(actual[key], expected[key], path + [key])
    elif isinstance(expected, list):
        assert isinstance(actual, list), path
        assert len(actual) == len(expected), path
        for a, e in zip(actual, expected):
            _assert_matches(a, e, path + ["*"])
    else:
        assert actual == expected, path


def test_export_metadata__success(admin_client):
    session = get_session()
    stmt = select(db.Text).limit(1)
    text = session.scalars(stmt).first()

    resp = admin_client.post(
        "/admin/Text/task/export-metadata", data={"selected_ids": [str(text.id)]}
    )
    assert resp.status_code == 200
    assert resp.content_type == "application/json"

    data = json.loads(resp.data)
    assert "slug" in data[0]
    assert "title" in data[0]


def test_import_metadata__success(admin_client):
    resp = admin_client.get("/admin/Text/task/import-metadata")
    assert resp.status_code == 200

    session = get_session()
    stmt = select(db.Text).limit(1)
    text = session.scalars(stmt).first()
    text_id = text.id
    original_title = text.title
    original_header = text.header

    metadata = {
        "api_version": "1",
        "created_at": "2026-01-01T00:00:00Z",
        "collections": [],
        "texts": [
            {
                "slug": text.slug,
                "title": "Updated Title",
                "license": "CC0 1.0",
            }
        ],
    }

    json_data = json.dumps(metadata).encode("utf-8")

    try:
        resp = admin_client.post(
            "/admin/Text/task/import-metadata",
            data={
                "json_file": (io.BytesIO(json_data), "metadata.json"),
                "csrf_token": "fake_token",
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        session = get_session()
        text = session.get(db.Text, text_id)
        assert text.title == "Updated Title"
        assert text.license == "CC0 1.0"
    finally:
        text = session.get(db.Text, text_id)
        text.title = original_title
        text.header = original_header
        text.license = None
        session.commit()


def test_import_metadata__invalid_json(admin_client):
    invalid_data = b"not valid json{"

    resp = admin_client.post(
        "/admin/Text/task/import-metadata",
        data={
            "json_file": (io.BytesIO(invalid_data), "bad.json"),
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200


# Import dictionaries tests
def test_import_dictionaries__get(admin_client):
    resp = admin_client.get("/admin/Dictionary/task/import-dictionaries")
    assert resp.status_code == 200


def test_import_dictionaries__no_files(admin_client):
    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={"csrf_token": "fake_token"},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_import_dictionaries__non_xml_file(admin_client):
    invalid_file = b"This is not XML"

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [(io.BytesIO(invalid_file), "test.txt")],
            "slug_0": "test-dict",
            "title_0": "Test Dictionary",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Must be an XML file" in resp.data


def test_import_dictionaries__missing_slug(admin_client):
    xml_data = b'<?xml version="1.0"?><dictionary></dictionary>'

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [(io.BytesIO(xml_data), "test.xml")],
            "title_0": "Test Dictionary",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Slug is required" in resp.data


def test_import_dictionaries__missing_title(admin_client):
    xml_data = b'<?xml version="1.0"?><dictionary></dictionary>'

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [(io.BytesIO(xml_data), "test.xml")],
            "slug_0": "test-dict",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Title is required" in resp.data


def test_import_dictionaries__duplicate_slug(admin_client):
    session = get_session()

    existing_dict = db.Dictionary(slug="existing-dict", title="Existing Dictionary")
    session.add(existing_dict)
    session.commit()

    xml_data = b'<?xml version="1.0"?><dictionary></dictionary>'

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [(io.BytesIO(xml_data), "test.xml")],
            "slug_0": "existing-dict",
            "title_0": "Test Dictionary",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"already exists" in resp.data


def test_import_dictionaries__invalid_xml(admin_client):
    invalid_xml = b'<?xml version="1.0"?><dictionary><unclosed>'

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [(io.BytesIO(invalid_xml), "test.xml")],
            "slug_0": "test-dict",
            "title_0": "Test Dictionary",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_import_dictionaries__multiple_files(admin_client):
    xml_data1 = b'<?xml version="1.0"?><dictionary></dictionary>'
    xml_data2 = b'<?xml version="1.0"?><dictionary></dictionary>'

    resp = admin_client.post(
        "/admin/Dictionary/task/import-dictionaries",
        data={
            "xml_files": [
                (io.BytesIO(xml_data1), "dict1.xml"),
                (io.BytesIO(xml_data2), "dict2.xml"),
            ],
            "slug_0": "test-dict-1",
            "title_0": "Test Dictionary 1",
            "slug_1": "test-dict-2",
            "title_1": "Test Dictionary 2",
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_add_genre__no_selection(admin_client):
    resp = admin_client.post(
        "/admin/Text/task/add-genre",
        data={},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"No texts selected" in resp.data


def test_add_genre__get(admin_client):
    session = get_session()
    stmt = select(db.Text).limit(1)
    text = session.scalars(stmt).first()

    genre = db.Genre(name="Test Genre for Adding")
    session.add(genre)
    session.commit()

    resp = admin_client.post(
        "/admin/Text/task/add-genre",
        data={"selected_ids": [str(text.id)]},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_add_genre__full_workflow(admin_client):
    session = get_session()

    genre = db.Genre(name="Workflow Test Genre")
    session.add(genre)
    session.commit()
    genre_id = genre.id

    stmt = select(db.Text).filter_by(slug="pariksha")
    text = session.scalars(stmt).first()
    assert text is not None

    resp = admin_client.post(
        "/admin/Text/task/add-genre",
        data={
            "selected_ids": [str(text.id)],
            "genre_id": str(genre_id),
            "csrf_token": "fake_token",
        },
        follow_redirects=True,
    )

    assert resp.status_code in [200, 302, 400]


def test_import_projects_and_export_projects(admin_client):
    """import-export round trip."""

    # Create test data
    session = get_session()

    bot_user = session.query(db.User).filter_by(username="ambuda-bot").first()
    assert bot_user

    page_status = session.query(db.PageStatus).first()
    board = db.Board(title="Test Import Board")
    session.add(board)
    session.flush()

    user = session.query(db.User).first()

    export_project = db.Project(
        slug="test-roundtrip-project",
        display_title="Test Roundtrip Project",
        author="Test Author",
        editor="Test Editor",
        board_id=board.id,
    )
    session.add(export_project)
    session.flush()

    export_page = db.Page(
        project_id=export_project.id, slug="page-1", order=1, status_id=page_status.id
    )
    session.add(export_page)
    session.flush()

    pc_text = db.Text(
        slug="test-roundtrip-project",
        title="Test Roundtrip Title",
        language="sa",
        stage="stub",
    )
    session.add(pc_text)
    session.flush()

    pc_author = db.Author(slug="test-pc-author", name="Test PC Author")
    session.add(pc_author)
    session.flush()
    pc_text.author_id = pc_author.id

    publish_config = db.PublishConfig(
        project_id=export_project.id,
        text_id=pc_text.id,
    )
    session.add(publish_config)

    if user:
        revision = db.Revision(
            project_id=export_project.id,
            page_id=export_page.id,
            author_id=user.id,
            status_id=page_status.id,
            content="Test content",
            summary="Test summary",
        )
        session.add(revision)
    session.commit()

    # Export
    resp = admin_client.post(
        "/admin/Project/task/export-projects",
        data={"selected_ids": [str(export_project.id)]},
    )
    exported_data = json.loads(resp.data)

    json_project = None
    for p in exported_data["projects"]:
        if p.get("slug") == "test-roundtrip-project":
            json_project = p
            break
    assert json_project

    # Rename the project --> force creating a new project on import
    json_project["slug"] = "test-import-project"
    json_project["uuid"] = "test-uuid-import"

    import_data = {"projects": [json_project]}
    json_data = json.dumps(import_data).encode("utf-8")

    resp = admin_client.post(
        "/admin/Project/task/import-projects",
        data={
            "json_file": (io.BytesIO(json_data), "projects.json"),
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    session = get_session()
    stmt = select(db.Project).filter_by(slug="test-import-project")
    imported_project = session.scalars(stmt).first()
    assert imported_project is not None

    _assert_matches(
        serialize(imported_project),
        {
            "id": Any,
            "slug": "test-import-project",
            "uuid": "test-uuid-import",
            "display_title": "Test Roundtrip Project",
            "print_title": "",
            "author": "Test Author",
            "editor": "Test Editor",
            "publisher": "",
            "publication_year": "",
            "publication_location": "",
            "worldcat_link": "",
            "description": "",
            "notes": "",
            "page_numbers": "",
            "created_at": Any,
            "updated_at": Any,
            "board_id": Any,
            "creator_id": Any,
            "status": Any,
            "genre_id": None,
        },
    )

    assert len(imported_project.pages) == 1
    _assert_matches(
        serialize(imported_project.pages[0]),
        {
            "id": Any,
            "project_id": Any,
            "slug": "page-1",
            "uuid": Any,
            "order": 1,
            "version": 0,
            "ocr_bounding_boxes": None,
            "status_id": Any,
        },
    )

    assert len(imported_project.publish_configs) == 1
    _assert_matches(
        serialize(imported_project.publish_configs[0]),
        {
            "id": Any,
            "project_id": imported_project.id,
            "text_id": Any,
            "target": None,
        },
    )

    if user:
        assert len(imported_project.pages[0].revisions) == 1
        _assert_matches(
            serialize(imported_project.pages[0].revisions[0]),
            {
                "id": Any,
                "project_id": Any,
                "page_id": Any,
                "author_id": Any,
                "status_id": Any,
                "created_at": Any,
                "batch_id": Any,
                "summary": "Test summary",
                "content": "Test content",
            },
        )


# --- TextCollection export/import tests ---


def _create_collection(session, slug, title, parent_id=None, order=0, texts=None):
    """Helper to create a TextCollection."""
    coll = db.TextCollection(slug=slug, title=title, parent_id=parent_id, order=order)
    if texts:
        coll.texts = texts
    session.add(coll)
    session.flush()
    return coll


def test_export_collections__success(admin_client):
    session = get_session()
    text = session.query(db.Text).first()

    parent = _create_collection(session, "export-parent", "Export Parent")
    child = _create_collection(
        session,
        "export-child",
        "Export Child",
        parent_id=parent.id,
        order=1,
        texts=[text] if text else None,
    )
    session.commit()

    resp = admin_client.post(
        "/admin/TextCollection/task/export-collections",
        data={"selected_ids": [str(parent.id), str(child.id)]},
    )
    assert resp.status_code == 200
    assert resp.content_type == "application/json"

    data = CollectionExportData.model_validate_json(resp.data)
    slugs = {c.slug for c in data.collections}
    assert "export-parent" in slugs
    assert "export-child" in slugs

    child_export = next(c for c in data.collections if c.slug == "export-child")
    assert child_export.parent_slug == "export-parent"
    assert child_export.order == 1
    if text:
        assert text.slug in child_export.text_slugs

    parent_export = next(c for c in data.collections if c.slug == "export-parent")
    assert parent_export.parent_slug is None


def test_export_collections__empty_selection(admin_client):
    resp = admin_client.post(
        "/admin/TextCollection/task/export-collections",
        data={"selected_ids": []},
    )
    assert resp.status_code == 200
    data = CollectionExportData.model_validate_json(resp.data)
    assert data.collections == []


def test_import_collections__get(admin_client):
    resp = admin_client.get("/admin/TextCollection/task/import-collections")
    assert resp.status_code == 200


def test_import_collections__round_trip(admin_client):
    """Export collections, then re-import them under new slugs."""
    session = get_session()

    text = session.query(db.Text).first()
    parent = _create_collection(session, "rt-parent", "RT Parent")
    child = _create_collection(
        session,
        "rt-child",
        "RT Child",
        parent_id=parent.id,
        order=2,
        texts=[text] if text else None,
    )
    session.commit()

    # Export
    resp = admin_client.post(
        "/admin/TextCollection/task/export-collections",
        data={"selected_ids": [str(parent.id), str(child.id)]},
    )
    data = CollectionExportData.model_validate_json(resp.data)

    # Rename slugs so import creates new collections
    for c in data.collections:
        if c.slug == "rt-parent":
            c.slug = "rt-parent-imported"
        if c.slug == "rt-child":
            c.slug = "rt-child-imported"
            c.parent_slug = "rt-parent-imported"

    json_data = data.model_dump_json().encode("utf-8")

    # Import
    resp = admin_client.post(
        "/admin/TextCollection/task/import-collections",
        data={
            "json_file": (io.BytesIO(json_data), "collections.json"),
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    session = get_session()
    imported_parent = (
        session.query(db.TextCollection).filter_by(slug="rt-parent-imported").first()
    )
    imported_child = (
        session.query(db.TextCollection).filter_by(slug="rt-child-imported").first()
    )
    assert imported_parent is not None
    assert imported_child is not None
    assert imported_child.parent_id == imported_parent.id
    assert imported_child.order == 2

    if text:
        assert text.slug in [t.slug for t in imported_child.texts]


def test_import_collections__updates_existing(admin_client):
    """Import over an existing slug should update it, not duplicate."""
    session = get_session()
    existing = _create_collection(session, "update-me", "Old Title", order=0)
    session.commit()
    existing_id = existing.id

    import_data = CollectionExportData(
        collections=[
            {
                "slug": "update-me",
                "title": "New Title",
                "order": 5,
                "description": "Updated desc",
            }
        ]
    )
    json_data = import_data.model_dump_json().encode("utf-8")

    resp = admin_client.post(
        "/admin/TextCollection/task/import-collections",
        data={
            "json_file": (io.BytesIO(json_data), "collections.json"),
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    session = get_session()
    updated = session.query(db.TextCollection).filter_by(slug="update-me").first()
    assert updated.id == existing_id
    assert updated.title == "New Title"
    assert updated.order == 5
    assert updated.description == "Updated desc"


def test_import_collections__invalid_json(admin_client):
    resp = admin_client.post(
        "/admin/TextCollection/task/import-collections",
        data={
            "json_file": (io.BytesIO(b"not valid json{"), "bad.json"),
            "csrf_token": "fake_token",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Error importing collections" in resp.data


def test_import_collections__no_file(admin_client):
    resp = admin_client.post(
        "/admin/TextCollection/task/import-collections",
        data={"csrf_token": "fake_token"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
