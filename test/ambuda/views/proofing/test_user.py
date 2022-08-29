def test_summary(client):
    resp = client.get("/proofing/users/akprasad/")
    assert resp.status_code == 200


def test_summary__missing(client):
    resp = client.get("/proofing/users/bad-user/")
    assert resp.status_code == 404


def test_activity(client):
    resp = client.get("/proofing/users/akprasad/activity")
    assert resp.status_code == 200


def test_activity__missing(client):
    resp = client.get("/proofing/users/bad-user/activity")
    assert resp.status_code == 404


def test_admin(admin_client):
    resp = admin_client.get("/proofing/users/akprasad/admin")
    assert resp.status_code == 200


def test_admin__unauth(rama_client):
    resp = rama_client.get("/proofing/users/akprasad/admin")
    assert resp.status_code == 302


def test_admin__missing(admin_client):
    resp = admin_client.get("/proofing/users/bad-user/admin")
    assert resp.status_code == 404
