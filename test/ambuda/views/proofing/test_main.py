import io

import pytest

from ambuda.views.proofing import main


@pytest.mark.parametrize(
    "path,expected",
    [
        ("book.pdf", True),
        ("book.djvu", False),
        ("book.epub", False),
    ],
)
def test_is_allowed_document_file(path, expected):
    assert main._is_allowed_document_file(path) == expected


def test_index(client):
    resp = client.get("/proofing/")
    assert resp.status_code == 200
    assert ">Proofing<" in resp.text


def test_complete_guide(client):
    resp = client.get("/proofing/help/complete-guide")
    assert "Complete guide" in resp.text


def test_recent_changes(client):
    resp = client.get("/proofing/recent-changes")
    assert "Recent changes" in resp.text


def test_create_project__unauth(client):
    resp = client.get("/proofing/create-project")
    assert resp.status_code == 302


def test_create_project__auth(rama_client):
    resp = rama_client.get("/proofing/create-project")
    assert resp.status_code == 200


def test_create_project__oversized_pdf(rama_client):
    from unittest.mock import patch
    from tempfile import SpooledTemporaryFile

    limit = 128 * 1024 * 1024

    original_tell = SpooledTemporaryFile.tell

    def fake_tell(self):
        pos = original_tell(self)
        self.seek(0, 2)
        end = original_tell(self)
        self.seek(pos)
        if pos == end and end > 0:
            return limit + 1
        return pos

    fake_pdf = io.BytesIO(b"%PDF-1.4 fake")

    with patch.object(SpooledTemporaryFile, "tell", fake_tell):
        resp = rama_client.post(
            "/proofing/create-project",
            data={
                "pdf_source": "local",
                "local_file": (fake_pdf, "big.pdf"),
                "display_title": "Test Project",
            },
            content_type="multipart/form-data",
        )
    assert resp.status_code == 200
    assert "PDF must be under 128 MB" in resp.text


def test_talk(client):
    resp = client.get("/proofing/talk")
    assert "Talk" in resp.text


def test_create_text__unauth(client):
    resp = client.get("/proofing/texts/new")
    assert resp.status_code == 302


def test_create_text__auth_renders_form(rama_client):
    resp = rama_client.get("/proofing/texts/new")
    assert resp.status_code == 200
    assert b"Create text" in resp.data


def _cleanup_created_text(slug):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.models.proofing import PublishConfig
    from ambuda.queries import get_session

    session = get_session()
    text = session.execute(select(db.Text).filter_by(slug=slug)).scalar_one_or_none()
    if text:
        session.execute(
            PublishConfig.__table__.delete().where(PublishConfig.text_id == text.id)
        )
        session.delete(text)
    session.commit()


def test_create_text__creates_text_and_publish_config(rama_client):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.models.proofing import PublishConfig
    from ambuda.models.texts import TextStage
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    try:
        resp = rama_client.post(
            "/proofing/texts/new",
            data={
                "project_id": project.id,
                "slug": "wizard-text",
                "title": "Wizard Text",
                "target": "(image 1 5)",
                "language": "sa",
                "author": "",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        session = get_session()
        text = session.execute(
            select(db.Text).filter_by(slug="wizard-text")
        ).scalar_one_or_none()
        assert text is not None
        assert text.title == "Wizard Text"
        assert text.stage == TextStage.STUB
        assert text.project_id == project.id

        pc = session.execute(
            select(PublishConfig).where(PublishConfig.text_id == text.id)
        ).scalar_one()
        assert pc.target == "(image 1 5)"
        assert pc.project_id == project.id
    finally:
        _cleanup_created_text("wizard-text")


def test_create_text__rejects_invalid_filter(rama_client):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    resp = rama_client.post(
        "/proofing/texts/new",
        data={
            "project_id": project.id,
            "slug": "bad-filter-text",
            "title": "Bad Filter",
            "target": "(image 1",
            "language": "sa",
        },
    )
    assert resp.status_code == 200

    session = get_session()
    text = session.execute(
        select(db.Text).filter_by(slug="bad-filter-text")
    ).scalar_one_or_none()
    assert text is None


def test_create_text__rejects_slug_conflict(rama_client, flask_app):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    flask_app.config["TESTING"] = False
    try:
        rama_client.post(
            "/proofing/texts/new",
            data={
                "project_id": project.id,
                "slug": "pariksha",
                "title": "Conflict",
                "target": "(image 1)",
                "language": "sa",
            },
        )
    finally:
        flask_app.config["TESTING"] = True

    session = get_session()
    pariksha = session.execute(select(db.Text).filter_by(slug="pariksha")).scalar_one()
    # Existing text was not overwritten — title should not match the form.
    assert pariksha.title != "Conflict"


def test_create_text__requires_target(rama_client):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    resp = rama_client.post(
        "/proofing/texts/new",
        data={
            "project_id": project.id,
            "slug": "no-target-text",
            "title": "No Target",
            "target": "",
            "language": "sa",
        },
    )
    assert resp.status_code == 200

    session = get_session()
    text = session.execute(
        select(db.Text).filter_by(slug="no-target-text")
    ).scalar_one_or_none()
    assert text is None


def test_create_text__attaches_collections_and_parent(rama_client):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.models.texts import TextStage
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    coll = db.TextCollection(slug="wizard-coll", title="Wizard Coll")
    parent = db.Text(
        slug="wizard-parent", title="Wizard Parent", language="sa", stage=TextStage.STUB
    )
    session.add_all([coll, parent])
    session.commit()
    coll_id = coll.id

    try:
        resp = rama_client.post(
            "/proofing/texts/new",
            data={
                "project_id": project.id,
                "slug": "wizard-child",
                "title": "Wizard Child",
                "target": "(image 1)",
                "language": "sa",
                "parent_slug": "wizard-parent",
                "collection_ids": [str(coll_id)],
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302

        session = get_session()
        text = session.execute(
            select(db.Text).filter_by(slug="wizard-child")
        ).scalar_one()
        assert text.parent.slug == "wizard-parent"
        assert [c.id for c in text.collections] == [coll_id]
    finally:
        _cleanup_created_text("wizard-child")
        session = get_session()
        session.execute(
            db.Text.__table__.delete().where(db.Text.slug == "wizard-parent")
        )
        session.execute(
            db.TextCollection.__table__.delete().where(
                db.TextCollection.slug == "wizard-coll"
            )
        )
        session.commit()


def test_unpublished_projects__unauth_redirects(client):
    resp = client.get("/proofing/admin/unpublished-projects")
    assert resp.status_code == 302


def test_unpublished_projects__p2_renders(rama_client):
    resp = rama_client.get("/proofing/admin/unpublished-projects")
    assert resp.status_code == 200
    assert b"Unpublished projects" in resp.data


def test_unpublished_projects__admin_renders(admin_client):
    resp = admin_client.get("/proofing/admin/unpublished-projects")
    assert resp.status_code == 200
    assert b"Unpublished projects" in resp.data


def test_unpublished_project_detail__renders_when_no_report(admin_client):
    resp = admin_client.get("/proofing/admin/unpublished-projects/test-project")
    assert resp.status_code == 200
    assert b"No report yet" in resp.data


def test_unpublished_project_detail__renders_blocks_when_report_exists(
    admin_client, flask_app
):
    from datetime import UTC, datetime
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    # Insert a fake report.
    session.execute(
        db.ProjectUncoveredReport.__table__.delete().where(
            db.ProjectUncoveredReport.project_id == project.id
        )
    )
    session.add(
        db.ProjectUncoveredReport(
            project_id=project.id,
            generated_at=datetime.now(UTC),
            payload={
                "blocks": [
                    {
                        "page_slug": "1",
                        "image_number": 1,
                        "block_index": 0,
                        "block_tag": "p",
                        "block_text": "lonely block",
                    }
                ]
            },
        )
    )
    session.commit()

    try:
        resp = admin_client.get("/proofing/admin/unpublished-projects/test-project")
        assert resp.status_code == 200
        assert b"lonely block" in resp.data
    finally:
        session = get_session()
        session.execute(
            db.ProjectUncoveredReport.__table__.delete().where(
                db.ProjectUncoveredReport.project_id == project.id
            )
        )
        session.commit()


def test_unpublished_project_detail__refresh_dispatches_task(admin_client):
    from unittest.mock import patch

    with patch(
        "ambuda.tasks.uncovered_reports.maybe_rerun_report", return_value=True
    ) as mock:
        resp = admin_client.post(
            "/proofing/admin/unpublished-projects/test-project/refresh",
            data={"csrf_token": ""},
        )
    assert resp.status_code == 302
    mock.assert_called_once()


def test_unpublished_projects__refresh_all_dispatches_per_project(admin_client):
    from unittest.mock import patch
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    num_projects = session.execute(select(db.Project)).scalars().all()

    with patch(
        "ambuda.tasks.uncovered_reports.maybe_rerun_report", return_value=True
    ) as mock:
        resp = admin_client.post(
            "/proofing/admin/unpublished-projects/refresh-all",
            data={"csrf_token": ""},
        )
    assert resp.status_code == 302
    assert mock.call_count == len(num_projects)


def test_unpublished_projects__lists_every_project(admin_client, flask_app):
    """The page lists every project, even those without a cached report."""
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    projects = session.execute(select(db.Project)).scalars().all()

    resp = admin_client.get("/proofing/admin/unpublished-projects")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    for p in projects:
        assert p.display_title in body


def test_create_text__rejects_unknown_parent_slug(rama_client):
    from sqlalchemy import select
    from ambuda import database as db
    from ambuda.queries import get_session

    session = get_session()
    project = session.execute(
        select(db.Project).filter_by(slug="test-project")
    ).scalar_one()

    resp = rama_client.post(
        "/proofing/texts/new",
        data={
            "project_id": project.id,
            "slug": "orphan-child",
            "title": "Orphan",
            "target": "(image 1)",
            "language": "sa",
            "parent_slug": "this-slug-does-not-exist",
        },
    )
    assert resp.status_code == 200

    session = get_session()
    assert (
        session.execute(
            select(db.Text).filter_by(slug="orphan-child")
        ).scalar_one_or_none()
        is None
    )
