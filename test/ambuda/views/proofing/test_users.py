def test_user(client):
    resp = client.get("/proofing/users/akprasad/")
    assert resp.status_code == 200


def test_user__missing(client):
    resp = client.get("/proofing/users/bad-user/")
    assert resp.status_code == 404


def test_user_edits(client):
    resp = client.get("/proofing/users/akprasad/edits")
    assert resp.status_code == 200


def test_user_edits__missing(client):
    resp = client.get("/proofing/users/bad-user/edits")
    assert resp.status_code == 404


def test_user_admin(admin_client):
    resp = admin_client.get("/proofing/users/akprasad/admin")
    assert resp.status_code == 200


def test_user_admin__unauth(rama_client):
    resp = rama_client.get("/proofing/users/akprasad/admin")
    assert resp.status_code == 302


def test_user_admin__missing(admin_client):
    resp = admin_client.get("/proofing/users/bad-user/admin")
    assert resp.status_code == 404
