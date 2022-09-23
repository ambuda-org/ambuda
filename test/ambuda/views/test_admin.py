def test_admin_index__unauth(client):
    resp = client.get("/admin/")
    assert resp.status_code == 404


def test_admin_index__auth(admin_client):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200


def test_admin_index__inactive(deleted_client, banned_client):
    assert deleted_client.get("/admin/").status_code == 404
    assert banned_client.get("/admin/").status_code == 404


def test_admin_text__unauth(client):
    resp = client.get("/admin/text/")
    assert resp.status_code == 404


def test_admin_text__inactive(deleted_client, banned_client):
    assert deleted_client.get("/admin/text/").status_code == 404
    assert banned_client.get("/admin/text/").status_code == 404
