def test_board(client):
    resp = client.get("/proofing/test-project/talk/")
    assert "Talk:" in resp.text


def test_board__bad_project(client):
    resp = client.get("/proofing/bad-project/talk/")
    assert resp.status_code == 404


def test_thread(client):
    resp = client.get("/proofing/test-project/talk/1")
    assert resp.status_code == 200


def test_thread__bad_project(client):
    resp = client.get("/proofing/bad-project/talk/1")
    assert resp.status_code == 404


def test_thread__bad_thread(client):
    resp = client.get("/proofing/test-project/talk/unknown")
    assert resp.status_code == 404


def test_create_thread(rama_client):
    resp = rama_client.get("/proofing/test-project/talk/create-thread")
    assert "create thread" in resp.text


def test_create_thread__bad_project(rama_client):
    resp = rama_client.get("/proofing/bad-project/talk/create-thread")
    assert resp.status_code == 404


def test_create_thread__unauth(client):
    resp = client.get("/proofing/test-project/talk/create-thread")
    assert resp.status_code == 302
    assert "/sign-in" in resp.text


def test_create_post(rama_client):
    resp = rama_client.get("/proofing/test-project/talk/1/create")
    assert "Create post" in resp.text


def test_create_post__bad_project(rama_client):
    resp = rama_client.get("/proofing/test-project/talk/1/create")
    assert resp.status_code == 404


def test_create_post__missing_project(rama_client):
    resp = rama_client.get("/proofing/test-project/talk/108/create")
    assert resp.status_code == 404


def test_create_post__unauth(client):
    resp = client.get("/proofing/test-project/talk/1/create")
    assert resp.status_code == 302
    assert "/sign-in" in resp.text


def test_edit_post(admin_client):
    resp = admin_client.get("/proofing/test-project/talk/1/1/edit")
    assert resp.status_code == 200


def test_edit_post__bad_project(admin_client):
    resp = admin_client.get("/proofing/bad-project/talk/1/1/edit")
    assert resp.status_code == 404


def test_edit_post__bad_thread(admin_client):
    resp = admin_client.get("/proofing/test-project/talk/bad-thread/1/edit")
    assert resp.status_code == 404


def test_edit_post__bad_post(admin_client):
    resp = admin_client.get("/proofing/test-project/talk/1/bad-post/edit")
    assert resp.status_code == 404


def test_edit_post__wrong_user(rama_client):
    resp = rama_client.get("/proofing/test-project/talk/1/1/edit")
    assert resp.status_code == 403


def test_edit_post__unauth(client):
    resp = client.get("/proofing/test-project/talk/1/1/edit")
    assert resp.status_code == 302
