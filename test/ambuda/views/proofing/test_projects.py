def test_summary(client):
    resp = client.get("/proofing/test-project/")
    assert resp.status_code == 200


def test_talk(client):
    resp = client.get("/proofing/test-project/talk/")
    assert "Talk:" in resp.text


def test_edit__unauth(client):
    resp = client.get("/proofing/test-project/edit")
    assert resp.status_code == 302


def test_edit__auth(rama_client):
    resp = rama_client.get("/proofing/test-project/edit")
    assert "Edit:" in resp.text


def test_download(client):
    resp = client.get("/proofing/test-project/download/")
    assert resp.status_code == 200


def test_download_as_text(client):
    resp = client.get("/proofing/test-project/download/text")
    assert resp.status_code == 200


def test_download_as_xml(client):
    resp = client.get("/proofing/test-project/download/xml")
    assert resp.status_code == 200


def test_admin__unauth(client):
    resp = client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__auth_no_admin(rama_client):
    resp = rama_client.get("/proofing/test-project/admin")
    assert resp.status_code == 302


def test_admin__auth_is_admin(admin_client):
    resp = admin_client.get("/proofing/test-project/admin")
    assert resp.status_code == 200
    assert "Admin:" in resp.text
