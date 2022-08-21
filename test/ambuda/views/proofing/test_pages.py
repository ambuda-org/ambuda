from ambuda.views.proofing import pages


def test_get_image_filesystem_path(flask_app):
    with flask_app.app_context():
        path = pages._get_image_filesystem_path("project", "1")
    assert path.match("**/project/pages/1.jpg")


def test_edit__unauth(client):
    r = client.get("/proofing/test-project/1/")
    assert "Since you are not logged in" in r.text


def test_edit__auth(rama_client):
    r = rama_client.get("/proofing/test-project/1/")
    assert "Publish changes" in r.text


def test_edit__bad_project(client):
    r = client.get("/proofing/unknown/1/")
    assert r.status_code == 404


def test_edit__bad_page(client):
    r = client.get("/proofing/test-project/unknown/")
    assert r.status_code == 404


def test_history(client):
    r = client.get("/proofing/test-project/1/history")
    assert "History:" in r.text


def test_history__bad_project(client):
    r = client.get("/proofing/unknown/1/history")
    assert r.status_code == 404


def test_history__bad_page(client):
    r = client.get("/proofing/test-project/unknown/history")
    assert r.status_code == 404


def test_revision(client):
    r = client.get("/proofing/test-project/1/revision/1")
    assert "Revision:" in r.text


def test_revision__bad_project(client):
    r = client.get("/proofing/unknown/1/revision/1")
    assert r.status_code == 404


def test_revision__bad_page(client):
    r = client.get("/proofing/test-project/unknown/revision/1")
    assert r.status_code == 404


def test_revision__bad_revision(client):
    r = client.get("/proofing/test-project/1/revision/4000")
    assert r.status_code == 404


def test_revision__bad_revision_non_numeric(client):
    r = client.get("/proofing/test-project/1/revision/unknown")
    assert r.status_code == 404
