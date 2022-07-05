def test_index(client):
    resp = client.get("/dictionaries/")
    assert "Dictionary lookup</h1>" in resp.text


def test_version__known(client):
    # Nothing here yet, should just redirect
    resp = client.get("/dictionaries/test-dict/")
    assert resp.status_code == 302


def test_version__missing(client):
    resp = client.get("/dictionaries/unknown/")
    assert resp.status_code == 404


def test_entry(client):
    resp = client.get("/dictionaries/test-dict/agni")
    assert resp.status_code == 200


def test_entry__version_missing(client):
    resp = client.get("/dictionaries/unknown/agni")
    assert resp.status_code == 404
