def test_summary(client):
    resp = client.get("/proofing/users/u-admin/")
    assert resp.status_code == 200


def test_edit__user_match(rama_client):
    resp = rama_client.get("/proofing/users/u-basic/edit")
    assert resp.status_code == 200


def test_edit__user_match__post(rama_client):
    resp = rama_client.get("/proofing/users/u-basic/")
    assert resp.status_code == 200
    assert "Tell others who you are" in resp.text

    resp = rama_client.post(
        "/proofing/users/u-basic/edit", data={"description": "My description"}
    )
    assert resp.status_code == 302

    resp = rama_client.get("/proofing/users/u-basic/")
    assert resp.status_code == 200
    assert "My description" in resp.text


def test_edit__user_mismatch(rama_client):
    resp = rama_client.get("/proofing/users/u-admin/edit")
    assert resp.status_code == 403


def test_edit__user_does_not_exist(rama_client):
    resp = rama_client.get("/proofing/users/unknown/edit")
    assert resp.status_code == 404


def test_edit__unauth(client):
    resp = client.get("/proofing/users/u-basic/edit")
    assert resp.status_code == 302


def test_summary__missing(client):
    resp = client.get("/proofing/users/bad-user/")
    assert resp.status_code == 404


def test_activity(client):
    resp = client.get("/proofing/users/u-admin/activity")
    assert resp.status_code == 200


def test_activity__missing(client):
    resp = client.get("/proofing/users/bad-user/activity")
    assert resp.status_code == 404


def test_admin(admin_client):
    resp = admin_client.get("/proofing/users/u-admin/admin")
    assert resp.status_code == 200


def test_admin__unauth(rama_client):
    resp = rama_client.get("/proofing/users/u-admin/admin")
    assert resp.status_code == 302


def test_admin__missing(admin_client):
    resp = admin_client.get("/proofing/users/bad-user/admin")
    assert resp.status_code == 404
