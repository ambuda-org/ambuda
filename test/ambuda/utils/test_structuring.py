import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pytest

from ambuda.utils import project_structuring as s


P = s.ProofPage
B = s.ProofBlock


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<page></page>", []),
        # OK: block elements
        *[
            (f"<page><{tag}>foo</{tag}></page>", [])
            for tag in [
                "p",
                "verse",
                "footnote",
                "heading",
                "trailer",
                "title",
                "subtitle",
            ]
        ],
        # OK: inline elements
        *[
            (f"<page><p><{tag}>foo</{tag}></p></page>", [])
            for tag in [
                "error",
                "fix",
                "speaker",
                "stage",
                "ref",
                "flag",
                "chaya",
                "prakrit",
                "note",
                "add",
                "ellipsis",
                "quote",
            ]
        ],
        # OK: <break/> in p and verse
        ("<page><p>text<break/>more</p></page>", []),
        ("<page><verse>text<break/>more</verse></page>", []),
        # OK: <break type="..."/> with a block-type attribute
        ("<page><p>text<break type='trailer'/>more</p></page>", []),
        # OK: <hyphen/> in p and verse
        ("<page><p>text<hyphen/>more</p></page>", []),
        ("<page><verse>text<hyphen/>more</verse></page>", []),
        # ERR: <hyphen> with content (must be empty)
        ("<page><p><hyphen>content</hyphen></p></page>", ["void element"]),
        # ERR: <break> in heading (not allowed)
        ("<page><heading>text<break/>more</heading></page>", ["Unexpected.*break"]),
        # ERR: <break> with content (must be empty)
        ("<page><p><break>content</break></p></page>", ["void element"]),
        # ERR: unknown or unexpected tag
        ("<foo></foo>", ["must be 'page'"]),
        ("<page><unk>foo</unk></page>", ["Unexpected.*unk", "Unknown.*unk"]),
        ("<page><p><unk>foo</unk></p></page>", ["Unexpected.*unk", "Unknown.*unk"]),
        ("<page><p><verse>foo</verse></p></page>", ["Unexpected.*verse"]),
        # ERR: unknown or unexpected attribute
        ("<page unk='foo'></page>", ["Unexpected attribute.*unk"]),
        ("<page><p unk='foo'>foo</p></page>", ["Unexpected attribute.*unk"]),
    ],
)
def test_validate_proofing_xml(input, expected):
    actual = s.validate_proofing_xml(input)

    assert len(actual) == len(expected)
    for a, e in zip(actual, expected):
        assert re.search(e, a.message)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<p>test</p>", "test"),
        ("<p>test <a>foo</a></p>", "test <a>foo</a>"),
        ("<p>test <a>foo</a> bar</p>", "test <a>foo</a> bar"),
        ("<p><a>foo</a> bar</p>", "<a>foo</a> bar"),
        ("<p><a>foo</a> <b>bar</b></p>", "<a>foo</a> <b>bar</b>"),
        # Unicode
        ("<p>अ <a>अ</a> अ</p>", "अ <a>अ</a> अ"),
    ],
)
def test_inner_xml(input, expected):
    assert s._inner_xml(ET.fromstring(input)) == expected


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<page></page>", P(id=0, blocks=[])),
        (
            "<page><verse>अ</verse></page>",
            P(id=0, blocks=[B(type="verse", content="अ")]),
        ),
        (
            "<page><p>अ</p></page>",
            P(id=0, blocks=[B(type="p", content="अ")]),
        ),
        (
            "<page><p>अ<b>अ</b></p></page>",
            P(id=0, blocks=[B(type="p", content="अ<b>अ</b>")]),
        ),
        (
            '<page><p merge-next="true">अ</p></page>',
            P(id=0, blocks=[B(type="p", content="अ", merge_next=True)]),
        ),
        (
            '<page><p merge-next="false">अ</p></page>',
            P(id=0, blocks=[B(type="p", content="अ", merge_next=False)]),
        ),
        # Legacy behavior
        (
            '<page><p merge-text="true">अ</p></page>',
            P(id=0, blocks=[B(type="p", content="अ", merge_next=True)]),
        ),
    ],
)
def test_from_xml_string(input, expected):
    assert s.ProofPage._from_xml_string(input, 0) == expected


def test_from_content_and_page_id():
    text = """
    अ

    क<error></error><fix>ख</fix>ग

    अ ।
    क ॥

    [^1] क
    """
    text = "\n".join(x.strip() for x in text.splitlines())
    assert s.ProofPage.from_content_and_page_id(text, 0) == P(
        id=0,
        blocks=[
            B(type="p", content="अ\nक<error></error><fix>ख</fix>ग"),
            B(type="verse", content="अ ।\nक ॥"),
            B(type="p", content="[^1] क"),
        ],
    )


def test_from_content_and_page_id__bare_text_in_page():
    """<page>...</page> with bare text (no block elements) should still parse.

    Pre-XML projects sometimes store unstructured text directly inside the
    page tag. A naive XML parse yields zero blocks; we should fall back to
    plain-text splitting so the content survives the round-trip.
    """
    text = "<page>हरिः ओम् ।\n\nश्लोकः अ ।\nश्लोकः क ॥</page>"
    parsed = s.ProofPage.from_content_and_page_id(text, 0)
    assert parsed.blocks, "Expected non-empty blocks for bare-text-in-page input"
    # Round-tripping should preserve the original text content.
    rendered = parsed.to_xml_string()
    for fragment in ("हरिः ओम् ।", "श्लोकः अ ।", "श्लोकः क ॥"):
        assert fragment in rendered


@pytest.mark.parametrize(
    "input,expected",
    [
        # p
        ("foo", "<page>\n<p>foo</p>\n</page>"),
        ("foo।bar।\nbizbaf॥", "<page>\n<p>foo।bar।\nbizbaf॥</p>\n</page>"),
        # verse
        (
            "foo\nbar।\nbiz\nbaf॥",
            "<page>\n<verse>foo\nbar।\nbiz\nbaf॥</verse>\n</page>",
        ),
        ("foobar।\nbizbaf॥", "<page>\n<verse>foobar।\nbizbaf॥</verse>\n</page>"),
        # speaker
        ("foo- bar", "<page>\n<p><speaker>foo-</speaker> bar</p>\n</page>"),
        ("foo-", "<page>\n<p>foo-</p>\n</page>"),
        # stage
        ("(bar)", "<page>\n<p><stage>(bar)</stage></p>\n</page>"),
        ("foo (bar) biz", "<page>\n<p>foo <stage>(bar)</stage> biz</p>\n</page>"),
        (
            "foo\n(bar)\nbiz",
            "<page>\n<p>foo</p>\n<p><stage>(bar)</stage></p>\n<p>biz</p>\n</page>",
        ),
        # speaker and stage
        (
            "foo- (bar) biz",
            "<page>\n<p><speaker>foo-</speaker> <stage>(bar)</stage> biz</p>\n</page>",
        ),
        # chaya
        ("foo [bar]", "<page>\n<p>foo <chaya>[bar]</chaya></p>\n</page>"),
        ("foo [bar\nbiz]", "<page>\n<p>foo <chaya>[bar\nbiz]</chaya></p>\n</page>"),
    ],
)
def test_split_plain_text_to_blocks(input, expected):
    blocks = s.split_plain_text_to_blocks(
        input,
        match_chaya=True,
        match_stage=True,
        match_speaker=True,
    )
    assert P(id=0, blocks=blocks).to_xml_string() == expected


def test_to_plain_text_inlines_fix():
    page = P(
        id=0,
        blocks=[
            B(type="p", content="foo<fix>bar</fix>baz"),
            B(type="verse", content="क<fix>ख</fix>ग"),
        ],
    )
    assert s.to_plain_text([page]) == "foobarbaz\n\nकखग"


def test_to_plain_text_inlines_quote():
    page = P(
        id=0,
        blocks=[
            B(type="p", content="foo<quote>bar</quote>baz"),
            B(type="verse", content="क<quote>ख</quote>ग"),
        ],
    )
    assert s.to_plain_text([page]) == "foobarbaz\n\nकखग"


def test_to_plain_text_removes_error():
    page = P(
        id=0,
        blocks=[
            B(type="p", content="foo<error>bad</error>baz"),
            B(type="verse", content="क<error></error><fix>ख</fix>ग"),
        ],
    )
    assert s.to_plain_text([page]) == "foobaz\n\nकखग"
