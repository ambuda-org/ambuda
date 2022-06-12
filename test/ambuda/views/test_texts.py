from test_site import flask_app, client


def test_index(client):
    resp = client.get("/texts/")
    assert "<h1>Texts</h1>" in resp.text
