import pytest


@pytest.mark.skip(reason="Not available on prod yet.")
def test_index(client):
    resp = client.get("/proof/")
    assert ">Proofreading<" in resp.text


@pytest.mark.skip(reason="Not available on prod yet.")
def test_upload__unauth(client):
    resp = client.get("/proof/upload")
    assert resp.status_code == 302
