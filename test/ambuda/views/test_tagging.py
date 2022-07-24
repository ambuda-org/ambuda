def test_index(client):
    resp = client.get("/proofing/tagging/")
    assert ">Tagging<" in resp.text


def test_text(client):
    resp = client.get("/proofing/tagging/pariksha/")
    assert resp.status_code == 200


def test_text_section(client):
    resp = client.get("/proofing/tagging/pariksha/1/")
    assert resp.status_code == 200


def test_text_block(client):
    resp = client.get("/proofing/tagging/pariksha/blocks/1.1")
    assert resp.status_code == 200
