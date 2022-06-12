import pytest
from ambuda import create_app


@pytest.fixture()
def flask_app():
    app = create_app("testing")
    app.config.update({"TESTING": True})
    yield app


@pytest.fixture()
def client(flask_app):
    return flask_app.test_client()


def test_index(client):
    resp = client.get("/")
    assert "<dfn>Ambuda</dfn>" in resp.text


def test_about(client):
    resp = client.get("/about/")
    assert "<h1>About</h1>" in resp.text


def test_contact(client):
    resp = client.get("/contact/")
    assert "<h1>Contact</h1>" in resp.text
