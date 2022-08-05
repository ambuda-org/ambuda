def test_index(client):
    resp = client.get("/tools/dictionaries/")
    assert "Dictionary lookup</h1>" in resp.text


def test_version__known(client):
    # Nothing here yet, should just redirect
    resp = client.get("/tools/dictionaries/test-dict/")
    assert resp.status_code == 302


def test_version__missing(client):
    resp = client.get("/tools/dictionaries/unknown/")
    assert resp.status_code == 404


def test_entry(client):
    resp = client.get("/tools/dictionaries/test-dict/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text


def test_entry__bad_version(client):
    resp = client.get("/tools/dictionaries/unknown/agni")
    assert resp.status_code == 404


def test_entry__bad_key(client):
    resp = client.get("/tools/dictionaries/test-dict/unknown")
    assert resp.status_code == 200
    assert "No results found" in resp.text


def test_entry_htmx(client):
    resp = client.get("/api/dictionaries/test-dict/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text


def test_entry_htmx__bad_version(client):
    resp = client.get("/api/dictionaries/unknown/agni")
    assert resp.status_code == 404


def test_entry_htmx__bad_key(client):
    resp = client.get("/api/dictionaries/test-dict/unknown")
    assert resp.status_code == 200
    assert "No results found" in resp.text
