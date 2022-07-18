def test_register(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert ">Register for Ambuda<" in resp.text


def test_register__auth(rama_client):
    resp = rama_client.get("/register")
    assert resp.status_code == 302


def test_sign_in__unauth(client):
    resp = client.get("/sign-in")
    assert resp.status_code == 200
    assert ">Sign in to Ambuda<" in resp.text


def test_sign_in__auth(rama_client):
    resp = rama_client.get("/sign-in")
    assert resp.status_code == 302


def test_sign_out__unauth(client):
    resp = client.get("/sign-out")
    assert resp.status_code == 302
