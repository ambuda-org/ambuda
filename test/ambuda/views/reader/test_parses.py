from indic_transliteration import sanscript


def d(s) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def test_block(client):
    resp = client.get("/parses/pariksha/1.1")
    assert resp.status_code == 200
    assert d("agniH") in resp.text


def test_block__missing_text(client):
    resp = client.get("/parses/unknown/1.1")
    assert resp.status_code == 404


def test_block__missing_block(client):
    resp = client.get("/parses/pariksha/1.2")
    assert resp.status_code == 404


def test_block_parse_htmx(client):
    resp = client.get("/api/parses/pariksha/1.1")
    assert resp.status_code == 200
    assert d("agniH") in resp.text


def test_block_parse_htmx__missing_text(client):
    resp = client.get("/api/parses/unknown/1.1")
    assert resp.status_code == 404


def test_block_parse_htmx__missing_block(client):
    resp = client.get("/api/parses/pariksha/1.2")
    assert resp.status_code == 404
