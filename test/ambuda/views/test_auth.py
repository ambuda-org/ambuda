def test_register(client):
    resp = client.get("/register")
    assert ">Register for Ambuda<" in resp.text


def test_sign_in(client):
    resp = client.get("/sign-in")
    assert ">Sign in to Ambuda<" in resp.text
