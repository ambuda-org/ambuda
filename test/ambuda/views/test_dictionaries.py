import pytest


def test_index(client):
    resp = client.get("/tools/dictionaries/")
    assert "Dictionary lookup</h1>" in resp.text


def test_source__known(client):
    # Nothing here yet, should just redirect
    resp = client.get("/tools/dictionaries/dict-1/")
    assert resp.status_code == 302


def test_source__missing(client):
    resp = client.get("/tools/dictionaries/unknown/")
    assert resp.status_code == 404


def test_entry(client):
    resp = client.get("/tools/dictionaries/dict-1/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text


def test_entry__multiple_sources(client):
    resp = client.get("/tools/dictionaries/dict-1,dict-2/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text
    assert "ignis" in resp.text


def test_entry__bad_source(client):
    resp = client.get("/tools/dictionaries/unknown/agni")
    assert resp.status_code == 404


def test_entry__bad_key(client):
    resp = client.get("/tools/dictionaries/dict-1/unknown")
    assert resp.status_code == 200
    assert "No results found" in resp.text


def test_entry_htmx(client):
    resp = client.get("/api/dictionaries/dict-1/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text


def test_entry_htmx__multiple_sources(client):
    resp = client.get("/api/dictionaries/dict-1,dict-2/agni")
    assert resp.status_code == 200
    assert "fire" in resp.text
    assert "ignis" in resp.text


def test_entry_htmx__bad_source(client):
    resp = client.get("/api/dictionaries/unknown/agni")
    assert resp.status_code == 404


def test_entry_htmx__bad_key(client):
    resp = client.get("/api/dictionaries/dict-1/unknown")
    assert resp.status_code == 200
    assert "No results found" in resp.text


@pytest.mark.parametrize(
    "before,after",
    [
        ("/tools/dictionaries/?source=mw&q=deva", "/tools/dictionaries/mw/deva"),
        ("/tools/dictionaries/apte/?source=mw&q=deva", "/tools/dictionaries/mw/deva"),
        (
            "/tools/dictionaries/apte/nara?source=mw&q=deva",
            "/tools/dictionaries/mw/deva",
        ),
        ("/tools/dictionaries/apte/nara?source=mw", "/tools/dictionaries/mw/nara"),
        ("/tools/dictionaries/apte/nara?q=deva", "/tools/dictionaries/apte/deva"),
    ],
)
def test_handle_form_submission(client, before, after):
    resp = client.get(before)
    assert resp.location == after
