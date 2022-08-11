import pytest


def test_index(client):
    resp = client.get("/")
    assert "Explore the library" in resp.text


def test_about(client):
    resp = client.get("/about/")
    assert "<h1>About</h1>" in resp.text


def test_support(client):
    resp = client.get("/support")
    assert "<h1>Support</h1>" in resp.text


def test_404(client):
    resp = client.get("/unknown-page/")
    assert "<h1>Not Found" in resp.text
    assert resp.status_code == 404


def test_sentry_500_throws_error(client):
    with pytest.raises(ZeroDivisionError):
        resp = client.get("/test-sentry-500")
