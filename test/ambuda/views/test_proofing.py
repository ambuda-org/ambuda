import pytest


def test_index(client):
    resp = client.get("/proofing/")
    assert ">Proofreading<" in resp.text


def test_upload__unauth(client):
    resp = client.get("/proofing/upload")
    assert resp.status_code == 302
