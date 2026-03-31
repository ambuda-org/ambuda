import pytest
from vidyut.lipi import transliterate, Scheme

from ambuda.utils.metadata_catalog import _strip_or_none, _parse_source


def d(s) -> str:
    return transliterate(s, Scheme.HarvardKyoto, Scheme.Devanagari)


def test_index(client):
    resp = client.get("/texts/")
    assert ">Texts</h1>" in resp.text


def test_text(client):
    resp = client.get("/texts/pariksha/")
    assert resp.status_code == 200
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


def test_download_pdf__missing(client):
    resp = client.get("/texts/unknown-text/download-pdf")
    assert resp.status_code == 404


# -- _strip_or_none tests --


@pytest.mark.parametrize(
    "input,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("\n  ", None),
        ("\t\n", None),
        ("hello", "hello"),
        ("  hello  ", "hello"),
        (" foo bar ", "foo bar"),
    ],
)
def test_strip_or_none(input, expected):
    assert _strip_or_none(input) == expected


# -- _parse_source tests --

_HEADER_TEMPLATE = """\
<teiHeader>
  <fileDesc>
    <titleStmt><title>{title}</title></titleStmt>
    <publicationStmt><p/></publicationStmt>
    <sourceDesc>
      <bibl>
        <author>{author}</author>
        <editor>{editor}</editor>
        <publisher>{publisher}</publisher>
        <pubPlace>{pub_place}</pubPlace>
        <date>{date}</date>
      </bibl>
    </sourceDesc>
  </fileDesc>
</teiHeader>"""


def test_parse_source__strips_whitespace():
    header = _HEADER_TEMPLATE.format(
        title="  My Title  ",
        author="  Some Author  ",
        editor="   ",
        publisher="\n  ",
        pub_place="  City  ",
        date="  1900  ",
    )
    source = _parse_source(header)
    assert source is not None
    assert source.title == "My Title"
    assert source.author == "Some Author"
    assert source.editor is None
    assert source.publisher is None
    assert source.publisher_place == "City"
    assert source.publication_year == "1900"


def test_parse_source__all_whitespace_returns_none():
    header = _HEADER_TEMPLATE.format(
        title="Unknown",
        author="   ",
        editor="",
        publisher="\n",
        pub_place="  \t  ",
        date="   ",
    )
    source = _parse_source(header)
    assert source is None


def test_parse_source__none_input():
    assert _parse_source(None) is None


def test_parse_source__invalid_xml():
    assert _parse_source("<not-valid-xml") is None
