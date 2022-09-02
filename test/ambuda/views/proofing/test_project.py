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
    print(resp.headers["Location"] == "/proofing/test-project/")


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


def test_search(rama_client):
    resp = rama_client.get("/proofing/test-project/search")
    assert "Search:" in resp.text


def test_search__bad_project(rama_client):
    resp = rama_client.get("/proofing/unknown/search")
    assert resp.status_code == 404


def test_admin__unauth(client):
    resp = client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__no_admin(rama_client):
    resp = rama_client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__has_admin(admin_client):
    resp = admin_client.get("/proofing/test-project/admin")
    assert resp.status_code == 200
    assert "Admin:" in resp.text


def test_admin__has_admin__bad_project(admin_client):
    resp = admin_client.get("/proofing/unknown/admin")
    assert resp.status_code == 404
