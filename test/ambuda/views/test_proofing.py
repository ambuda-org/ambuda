def test_index(client):
    resp = client.get("/proofing/")
    assert ">Proofing<" in resp.text


def test_create_new_project__unauth(client):
    resp = client.get("/proofing/create-new-project")
    assert resp.status_code == 302


def test_create_new_project__auth(rama_client):
    resp = rama_client.get("/proofing/create-new-project")
    assert resp.status_code == 200


def test_project(client):
    resp = client.get("/proofing/test-project/")
    assert resp.status_code == 200


def test_download_as_text(client):
    resp = client.get("/proofing/test-project/download/text")
    assert resp.status_code == 200


def test_download_as_xml(client):
    resp = client.get("/proofing/test-project/download/xml")
    assert resp.status_code == 200


def test_edit_page__unauth(client):
    resp = client.get("/proofing/test-project/1/")
    assert resp.status_code == 302


def test_edit_page(rama_client):
    resp = rama_client.get("/proofing/test-project/1/")
    assert resp.status_code == 200


def test_page_history(client):
    resp = client.get("/proofing/test-project/1/history")
    assert resp.status_code == 200
