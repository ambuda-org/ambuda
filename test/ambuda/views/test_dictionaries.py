from test_site import flask_app, client


def test_index(client):
    resp = client.get("/dictionaries/")
    assert "Dictionary lookup</h1>" in resp.text


def test_unknown_dict(client):
    resp = client.get("/dictionaries/unknown-dict/")
    assert resp.status_code == 404
