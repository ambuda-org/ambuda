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


def test_download_as_xml(client):
    resp = client.get("/proofing/test-project/download/xml")
    assert resp.status_code == 200


def test_download_as_xml__bad_project(client):
    resp = client.get("/proofing/unknown/download/xml")
    assert resp.status_code == 404


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
