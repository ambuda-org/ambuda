def test_admin_index__unauth(client):
    resp = client.get("/admin/")
    assert resp.status_code == 404


def test_admin_text__unauth(client):
    resp = client.get("/admin/text/")
    assert resp.status_code == 404
