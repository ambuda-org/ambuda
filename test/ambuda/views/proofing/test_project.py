import json
from unittest.mock import patch

import ambuda.queries as q
from ambuda.database import Board, Page, Project


def _get_board_id():
    """Get the board_id from the existing test project."""
    session = q.get_session()
    project = session.query(Project).filter_by(slug="test-project").one()
    return project.board_id


def test_summary(client):
    resp = client.get("/proofing/test-project/")
    assert resp.status_code == 200


def test_summary__bad_project(client):
    resp = client.get("/proofing/unknown/")
    assert resp.status_code == 404


def test_activity(client):
    resp = client.get("/proofing/test-project/activity")
    assert resp.status_code == 200


def test_activity__bad_project(client):
    resp = client.get("/proofing/unknown/activity")
    assert resp.status_code == 404


# For "Talk:" tests, see test_talk.py.


def test_edit__unauth(client):
    resp = client.get("/proofing/test-project/edit")
    assert resp.status_code == 302


def test_edit__auth(rama_client):
    resp = rama_client.get("/proofing/test-project/edit")
    assert "Edit:" in resp.text


def test_edit__auth__post_succeeds(rama_client):
    resp = rama_client.post(
        "/proofing/test-project/edit",
        data={
            "description": "some description",
            "page_numbers": "",
            "title": "some title",
            "author": "some author",
            "editor": "",
            "publisher": "some publisher",
            "publication_year": "",
        },
    )
    assert resp.status_code == 302


def test_edit__auth__post_fails(rama_client):
    resp = rama_client.post(
        "/proofing/test-project/edit",
        data={
            # Bade page spec forces form to fail validation
            "page_numbers": "garbage in, garbage out",
        },
    )
    assert resp.status_code == 200.0
    assert "page number spec" in resp.text


def test_edit__auth__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/edit")
    assert resp.status_code == 404


def test_download(client):
    resp = client.get("/proofing/test-project/download/")
    assert resp.status_code == 200


def test_download__bad_project(client):
    resp = client.get("/proofing/unknown/download/")
    assert resp.status_code == 404


def test_download_as_text(client):
    resp = client.get("/proofing/test-project/download/text")
    assert resp.status_code == 200


def test_download_as_text__bad_project(client):
    resp = client.get("/proofing/unknown/download/text")
    assert resp.status_code == 404


def test_download_as_xml(rama_client):
    resp = rama_client.get("/proofing/test-project/download/xml")
    assert resp.status_code == 200
    assert resp.mimetype == "application/xml"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "test-project.xml" in resp.headers["Content-Disposition"]
    assert resp.text.startswith('<?xml version="1.0"')
    assert "<project>" in resp.text


def test_download_as_xml__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/download/xml")
    assert resp.status_code == 404


def test_download_snapshot(rama_client):
    resp = rama_client.get("/proofing/test-project/download/snapshot")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "test-project-snapshot.json" in resp.headers["Content-Disposition"]

    payload = resp.get_json()
    assert payload["slug"] == "test-project"
    assert "title" in payload
    assert "exported_at" in payload
    assert isinstance(payload["pages"], list)
    assert payload["pages"], "expected at least one page in fixture project"
    page = payload["pages"][0]
    assert set(page.keys()) == {
        "image_url",
        "content",
        "revision_id",
        "status",
        "updated_at",
    }


def test_download_snapshot__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/download/snapshot")
    assert resp.status_code == 404


def _import_round_trip(slug, revision_id, db_content):
    """Build the export wrapper for ``db_content`` and run it through the
    import classifier. Returns ``(item, page_xml)``."""
    from types import SimpleNamespace

    from ambuda.views.proofing.project import (
        _build_export_page_xml,
        _classify_import_pages,
    )

    page_xml = _build_export_page_xml(slug, revision_id, db_content)
    project_xml = f"<project>{page_xml}</project>"
    project = SimpleNamespace(
        pages=[
            SimpleNamespace(
                slug=slug,
                version=1,
                revisions=[SimpleNamespace(id=revision_id, content=db_content)],
            )
        ]
    )
    items, err = _classify_import_pages(project_xml, project)
    assert err is None
    assert len(items) == 1
    return items[0], page_xml


def test_export_import_round_trip_preserves_whitespace():
    """Canonical content with newlines between blocks and whitespace inside
    text nodes round-trips download → import as ``unchanged``.

    Regression: pretty-printing the project XML (e.g. via ``ET.indent`` on
    the whole tree) would propagate into each page's inner subtree,
    drifting from the canonical stored form and producing noisy
    whitespace diffs on re-import.
    """
    canonical = "<page>\n<verse>क  ख</verse>\n<p>line one\nline two</p>\n</page>"
    item, _ = _import_round_trip("001", 11, canonical)
    assert item["category"] == "unchanged", f"round-trip introduced a diff: {item}"


def test_export_inserts_line_breaks_for_readability():
    """Non-canonical stored content (no whitespace between blocks) is
    pretty-printed in the export so readers see the structure on
    separate lines, but the round-trip still classifies as ``unchanged``
    because the comparison normalizes formatting whitespace.
    """
    no_whitespace = "<page><verse>x</verse></page>"
    item, page_xml = _import_round_trip("001", 11, no_whitespace)

    # Pretty-print: block elements separated by newlines.
    assert "\n<verse>x</verse>\n" in page_xml, (
        f"expected line breaks around inner block elements; got:\n{page_xml}"
    )
    # No double-page wrapper: slug/revision attrs land on the existing
    # <page> root rather than nesting another <page> inside.
    assert "<page><page" not in page_xml.replace("\n", "")
    assert page_xml.strip().startswith('<page slug="001"')
    # Round-trip is whitespace-insensitive: no diff despite added formatting.
    assert item["category"] == "unchanged", (
        f"non-canonical round-trip should normalize cleanly: {item}"
    )


def test_stats(moderator_client, rama_client):
    resp = moderator_client.get("/proofing/test-project/stats")
    assert resp.status_code == 200
    assert "Roman characters" in resp.text

    resp = rama_client.get("/proofing/test-project/stats")
    assert resp.status_code == 302


def test_admin(moderator_client):
    session = q.get_session()

    project = Project(
        slug="project-123", display_title="Dummy project", board_id=_get_board_id()
    )
    session.add(project)
    session.commit()

    with patch("ambuda.tasks.projects.delete_project.apply_async") as mock_task:
        resp = moderator_client.post(
            "/proofing/project-123/admin",
            data={
                "slug": "project-123",
            },
        )
        # Redirect (to project index page) indicates success.
        assert resp.status_code == 302
        mock_task.assert_called_once()


def test_admin__slug_mismatch(moderator_client):
    session = q.get_session()

    project = Project(
        slug="project-1234", display_title="Dummy project", board_id=_get_board_id()
    )
    session.add(project)
    session.commit()

    # Deletion fails due to a mismatched `slug` value.
    resp = moderator_client.post(
        "/proofing/project-1234/admin",
        data={
            "slug": "project-aoeu",
        },
    )
    assert resp.status_code == 200
    assert "Deletion failed" in resp.text


def test_admin__unauth(client):
    resp = client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__no_admin(rama_client):
    resp = rama_client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__has_moderator_role(moderator_client):
    resp = moderator_client.get("/proofing/test-project/admin")
    assert resp.status_code == 200
    assert "Admin:" in resp.text


def test_admin__has_admin_role(admin_client):
    resp = admin_client.get("/proofing/test-project/admin")
    assert resp.status_code == 200
    assert "Admin:" in resp.text


def test_admin__has_moderator_role__bad_project(admin_client):
    resp = admin_client.get("/proofing/unknown/admin")
    assert resp.status_code == 404


def test_batch_ocr(moderator_client):
    resp = moderator_client.get("/proofing/test-project/batch-ocr")
    assert resp.status_code == 200


def test_batch_ocr__unauth(client):
    resp = client.get("/proofing/test-project/batch-ocr")
    assert resp.status_code == 302


_reorder_counter = 0


def _make_reorder_project():
    global _reorder_counter
    _reorder_counter += 1
    session = q.get_session()
    slug = f"reorder-proj-{_reorder_counter}"
    project = Project(slug=slug, display_title="Reorder", board_id=_get_board_id())
    session.add(project)
    session.flush()
    status_id = q.project("test-project").pages[0].status_id
    uuids = [
        f"uuid-{_reorder_counter}-aaa",
        f"uuid-{_reorder_counter}-bbb",
        f"uuid-{_reorder_counter}-ccc",
    ]
    pages = [
        Page(
            project_id=project.id,
            slug=f"r-{i}",
            order=i,
            status_id=status_id,
            uuid=uuids[i],
        )
        for i in range(3)
    ]
    session.add_all(pages)
    session.flush()
    return project, pages, uuids


def _post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type="application/json")


def test_reorder_pages__get(rama_client):
    resp = rama_client.get("/proofing/test-project/reorder-pages")
    assert resp.status_code == 200
    assert "Lock text to image" in resp.text


def test_reorder_pages__unauth(client):
    resp = client.get("/proofing/test-project/reorder-pages")
    assert resp.status_code == 302


def _get_pages(ids):
    session = q.get_session()
    return [session.get(Page, pid) for pid in ids]


def test_reorder_pages__post_order(rama_client):
    project, pages, uuids = _make_reorder_project()
    ids = [p.id for p in pages]
    resp = _post_json(
        rama_client,
        f"/proofing/{project.slug}/reorder-pages",
        {
            "page_ids": [ids[2], ids[0], ids[1]],
        },
    )
    assert resp.json["ok"]
    p0, p1, p2 = _get_pages(ids)
    assert p2.order < p0.order < p1.order


def test_reorder_pages__post_image_uuids(rama_client):
    project, pages, uuids = _make_reorder_project()
    ids = [p.id for p in pages]
    resp = _post_json(
        rama_client,
        f"/proofing/{project.slug}/reorder-pages",
        {
            "page_ids": [ids[0], ids[1], ids[2]],
            "image_uuids": [uuids[2], uuids[0], uuids[1]],
        },
    )
    assert resp.json["ok"]
    p0, p1, p2 = _get_pages(ids)
    assert p0.uuid == uuids[2]
    assert p1.uuid == uuids[0]
    assert p2.uuid == uuids[1]


def test_reorder_pages__invalid_page_ids(rama_client):
    project, _, _ = _make_reorder_project()
    resp = _post_json(
        rama_client,
        f"/proofing/{project.slug}/reorder-pages",
        {
            "page_ids": [999999],
        },
    )
    assert resp.status_code == 400
    assert "Invalid page IDs" in resp.json["error"]


def test_reorder_pages__invalid_image_uuids(rama_client):
    project, pages, uuids = _make_reorder_project()
    ids = [p.id for p in pages]
    resp = _post_json(
        rama_client,
        f"/proofing/{project.slug}/reorder-pages",
        {
            "page_ids": [ids[0], ids[1], ids[2]],
            "image_uuids": [uuids[0], uuids[1], "uuid-FAKE"],
        },
    )
    assert resp.status_code == 400
    assert "Invalid image UUIDs" in resp.json["error"]


def test_batch_status__unauth(client):
    resp = client.get("/proofing/test-project/tools/batch-status")
    assert resp.status_code == 302


def test_batch_status__no_p2(no_p1_client):
    resp = no_p1_client.get("/proofing/test-project/tools/batch-status")
    assert resp.status_code == 302


def test_batch_status__p2_get(rama_client):
    resp = rama_client.get("/proofing/test-project/tools/batch-status")
    assert resp.status_code == 200
    assert "Start image" in resp.text


def test_batch_status__p2_preview(rama_client):
    resp = rama_client.get(
        "/proofing/test-project/tools/batch-status?start=1&end=1&status_id=1"
    )
    assert resp.status_code == 200
    assert "Preview" in resp.text


def test_batch_status__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/tools/batch-status")
    assert resp.status_code == 404


def test_replace_pdf__unauth(client):
    resp = client.get("/proofing/test-project/replace-pdf")
    assert resp.status_code == 302


def test_replace_pdf__auth_get(rama_client):
    resp = rama_client.get("/proofing/test-project/replace-pdf")
    assert resp.status_code == 200
    assert "Replace PDF" in resp.text


def test_replace_pdf__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/replace-pdf")
    assert resp.status_code == 404
