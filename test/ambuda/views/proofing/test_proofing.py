def test_index(client):
    resp = client.get("/proofing/")
    assert ">Proofing<" in resp.text


def test_beginners_guide(client):
    resp = client.get("/proofing/beginners-guide")
    assert ">Beginner's" in resp.text


def test_guidelines(client):
    resp = client.get("/proofing/complete-guidelines")
    assert ">" in resp.text


def test_create_new_project__unauth(client):
    resp = client.get("/proofing/create-new-project")
    assert resp.status_code == 302


def test_create_new_project__auth(rama_client):
    resp = rama_client.get("/proofing/create-new-project")
    assert resp.status_code == 200


def test_edit_page__unauth(client):
    resp = client.get("/proofing/test-project/1/")
    assert resp.status_code == 200
    assert "not logged in" in resp.text


def test_edit_page(rama_client):
    resp = rama_client.get("/proofing/test-project/1/")
    assert resp.status_code == 200


def test_page_history(client):
    resp = client.get("/proofing/test-project/1/history")
    assert resp.status_code == 200
