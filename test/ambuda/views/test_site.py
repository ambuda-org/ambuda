import pytest

from ambuda.views.site import _normalize_hk


class TestNormalizeHK:
    """Test the HK normalization used for fuzzy text search."""

    def test_identity_for_simple_vowels(self):
        assert _normalize_hk("a") == "a"
        assert _normalize_hk("i") == "i"
        assert _normalize_hk("u") == "u"

    def test_aspirates_collapsed(self):
        assert _normalize_hk("kh") == "k"
        assert _normalize_hk("gh") == "g"
        assert _normalize_hk("ch") == "c"
        assert _normalize_hk("jh") == "j"
        assert _normalize_hk("Th") == "T"
        assert _normalize_hk("Dh") == "D"
        assert _normalize_hk("th") == "t"
        assert _normalize_hk("dh") == "d"
        assert _normalize_hk("ph") == "p"
        assert _normalize_hk("bh") == "b"

    def test_sibilants_collapsed(self):
        assert _normalize_hk("sh") == "s"
        assert _normalize_hk("z") == "s"

    def test_nasals_collapsed(self):
        assert _normalize_hk("G") == "n"
        assert _normalize_hk("J") == "n"
        assert _normalize_hk("M") == "n"
        assert _normalize_hk("m") == "n"

    def test_vowel_alternates(self):
        assert _normalize_hk("ee") == "i"
        assert _normalize_hk("oo") == "u"
        assert _normalize_hk("ou") == "au"

    def test_spaces_removed(self):
        assert _normalize_hk("mahA bhArata") == "nahAbArata"

    def test_full_word(self):
        # rAmAyaNa — no replacements needed except m→n
        assert _normalize_hk("rAmAyaNa") == "rAnAyaNa"

    def test_mahabharata_variants_match(self):
        a = _normalize_hk("mahAbhArata").lower()
        b = _normalize_hk("mahabharata").lower()
        assert a == b

    def test_ramayana_variants_match(self):
        a = _normalize_hk("rAmAyaNa").lower()
        b = _normalize_hk("ramayana").lower()
        assert a == b

    def test_empty_string(self):
        assert _normalize_hk("") == ""

    def test_no_match_passthrough(self):
        assert _normalize_hk("yoga") == "yoga"


def test_index(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_donate(client):
    resp = client.get("/donate")
    assert "Donate today" in resp.text


def test_donate_book(client):
    resp = client.get("/donate/my-book-title/100")
    assert "my-book-title" in resp.text


def test_sponsor(client):
    resp = client.get("/sponsor")
    assert "Sponsor a Book" in resp.text


def test_support(client):
    resp = client.get("/support")
    assert ">Support</h1>" in resp.text


def test_404(client):
    resp = client.get("/unknown-page/")
    assert "<h1>Not Found" in resp.text
    assert resp.status_code == 404


def test_sentry_500_throws_error(client):
    with pytest.raises(ZeroDivisionError):
        _ = client.get("/test-sentry-500")
