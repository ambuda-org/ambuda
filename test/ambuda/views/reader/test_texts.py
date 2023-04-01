from indic_transliteration import sanscript


def d(s) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def test_index(client):
    resp = client.get("/texts/")
    assert ">Texts</h1>" in resp.text


def test_text(client):
    resp = client.get("/texts/pariksha/")
    assert d("parIkSA") in resp.text


def test_text__missing(client):
    resp = client.get("/texts/unknown-text/")
    assert resp.status_code == 404


def test_about(client):
    resp = client.get("/texts/pariksha/about")
    assert resp.status_code == 200


def test_about__missing(client):
    resp = client.get("/texts/unknown-test/about")
    assert resp.status_code == 404


def test_resources(client):
    resp = client.get("/texts/pariksha/resources")
    assert resp.status_code == 200


def test_resources__missing(client):
    resp = client.get("/texts/unknown-test/resources")
    assert resp.status_code == 404


def test_section(client):
    resp = client.get("/texts/pariksha/1")
    assert resp.status_code == 200
    assert d("adhyAyaH 1") in resp.text


def test_section__text_missing(client):
    resp = client.get("/texts/unknown-text/2")
    assert resp.status_code == 404


def test_section__section_missing(client):
    resp = client.get("/texts/pariksha/3")
    assert resp.status_code == 404


def test_block_htmx(client):
    resp = client.get("/api/texts/pariksha/blocks/1.1")
    assert resp.status_code == 200
    # <div> becomes <section> through xml.py
    # Test is unchanged because we assume that the source text already in
    # Devanagari, so we don't apply transliteration.
    assert "<section>agniH</section>" in resp.text
