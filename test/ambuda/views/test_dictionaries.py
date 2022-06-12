from test_site import flask_app, client


def test_index(client):
    resp = client.get("/dictionaries/")
    assert "Dictionary lookup</h1>" in resp.text
