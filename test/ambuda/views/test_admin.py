def test_admin_index__unauth(client):
    resp = client.get("/admin/")
    assert resp.status_code == 404


def test_admin_index__auth_admin(admin_client):
    resp = admin_client.get("/admin/")
    assert resp.status_code == 200


def test_admin_index__auth_moderator(moderator_client):
    resp = moderator_client.get("/admin/")
    assert resp.status_code == 200


def test_admin_index__inactive(deleted_client, banned_client):
    assert deleted_client.get("/admin/").status_code == 404
    assert banned_client.get("/admin/").status_code == 404


def test_admin_text__unauth(client):
    resp = client.get("/admin/text/")
    assert resp.status_code == 404


def test_admin_text__admin_or_moderator(admin_client, moderator_client):
    resp = admin_client.get("/admin/projectsponsorship/")
    assert resp.status_code == 200

    resp = moderator_client.get("/admin/projectsponsorship/")
    assert resp.status_code == 200


def test_admin_text__admin_only(admin_client, moderator_client):
    resp = admin_client.get("/admin/text/")
    assert resp.status_code == 200

    resp = moderator_client.get("/admin/text/")
    assert resp.status_code == 404


def test_admin_text__inactive(deleted_client, banned_client):
    assert deleted_client.get("/admin/text/").status_code == 404
    assert banned_client.get("/admin/text/").status_code == 404
