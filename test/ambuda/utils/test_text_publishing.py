from lxml import etree
import pytest

from ambuda import database as db
from ambuda.enums import SitePageStatus
from ambuda.utils import text_publishing as s


# Utilities
# -------------------------------------------------------------------


def _make_block(image_number, block_index, page_xml_str):
    page_xml = etree.fromstring(page_xml_str)
    page_status = db.PageStatus(name=SitePageStatus.R1)
    revision = db.Revision(id=1, page_id=1, content=page_xml_str, status=page_status)
    return s.IndexedBlock(
        revision=revision,
        image_number=image_number,
        block_index=block_index,
        page_xml=page_xml,
    )


def test_filter_parse__rejects_deeply_nested_sexp():
    deeply_nested = "(" * 50 + "and" + ")" * 50
    with pytest.raises(ValueError, match="levels deep"):
        s.Filter(deeply_nested)


def test_filter_parse__rejects_missing_open_paren():
    with pytest.raises(ValueError, match="must start with"):
        s.Filter("image 1")


def test_filter_parse__rejects_missing_close_paren():
    with pytest.raises(ValueError, match="Missing closing parenthesis"):
        s.Filter("(image 1")


def test_filter_matches__image_single():
    f = s.Filter("(image 3)")
    block2 = _make_block(2, 0, "<page><p>a</p></page>")
    block3 = _make_block(3, 0, "<page><p>a</p></page>")
    block4 = _make_block(4, 0, "<page><p>a</p></page>")
    assert not f.matches(block2)
    assert f.matches(block3)
    assert not f.matches(block4)


def test_filter_matches__image_range():
    f = s.Filter("(image 2 4)")
    block1 = _make_block(1, 0, "<page><p>a</p></page>")
    block2 = _make_block(2, 0, "<page><p>a</p></page>")
    block3 = _make_block(3, 0, "<page><p>a</p></page>")
    block4 = _make_block(4, 0, "<page><p>a</p></page>")
    block5 = _make_block(5, 0, "<page><p>a</p></page>")
    assert not f.matches(block1)
    assert f.matches(block2)
    assert f.matches(block3)
    assert f.matches(block4)
    assert not f.matches(block5)


def test_filter_matches__page_alias():
    f = s.Filter("(page 3)")
    block3 = _make_block(3, 0, "<page><p>a</p></page>")
    assert f.matches(block3)


def test_filter_matches__label():
    f = s.Filter("(label foo)")
    block_match = _make_block(1, 0, '<page><p text="foo">a</p></page>')
    block_no_match = _make_block(1, 0, '<page><p text="bar">a</p></page>')
    block_no_attr = _make_block(1, 0, "<page><p>a</p></page>")
    assert f.matches(block_match)
    assert not f.matches(block_no_match)
    assert not f.matches(block_no_attr)


def test_filter_matches__label_second_block():
    f = s.Filter("(label bar)")
    block = _make_block(1, 1, '<page><p text="foo">a</p><p text="bar">b</p></page>')
    assert f.matches(block)


def test_filter_matches__tag():
    f = s.Filter("(tag p)")
    block_p = _make_block(1, 0, "<page><p>a</p></page>")
    block_verse = _make_block(1, 0, "<page><verse>a</verse></page>")
    assert f.matches(block_p)
    assert not f.matches(block_verse)


def test_filter_matches__and():
    f = s.Filter("(and (image 2 4) (tag p))")
    block_match = _make_block(3, 0, "<page><p>a</p></page>")
    block_wrong_tag = _make_block(3, 0, "<page><verse>a</verse></page>")
    block_wrong_image = _make_block(1, 0, "<page><p>a</p></page>")
    assert f.matches(block_match)
    assert not f.matches(block_wrong_tag)
    assert not f.matches(block_wrong_image)


def test_filter_matches__or():
    f = s.Filter("(or (image 1) (image 3))")
    block1 = _make_block(1, 0, "<page><p>a</p></page>")
    block2 = _make_block(2, 0, "<page><p>a</p></page>")
    block3 = _make_block(3, 0, "<page><p>a</p></page>")
    assert f.matches(block1)
    assert not f.matches(block2)
    assert f.matches(block3)


def test_filter_matches__not():
    f = s.Filter("(not (image 2))")
    block1 = _make_block(1, 0, "<page><p>a</p></page>")
    block2 = _make_block(2, 0, "<page><p>a</p></page>")
    block3 = _make_block(3, 0, "<page><p>a</p></page>")
    assert f.matches(block1)
    assert not f.matches(block2)
    assert f.matches(block3)


def test_filter_matches__empty_and():
    f = s.Filter("(and)")
    block = _make_block(1, 0, "<page><p>a</p></page>")
    assert f.matches(block)


def test_filter_matches__image_single_with_label():
    f = s.Filter("(image 3:foo)")
    page = '<page><p text="foo">a</p><p text="bar">b</p></page>'
    assert f.matches(_make_block(3, 0, page))
    assert not f.matches(_make_block(3, 1, page))
    assert not f.matches(_make_block(2, 0, '<page><p text="foo">a</p></page>'))


def test_filter_matches__image_range_with_labels():
    f = s.Filter("(image 2:start 4:end)")
    assert not f.matches(_make_block(1, 0, '<page><p text="x">a</p></page>'))
    page2 = (
        '<page><p text="before">a</p><p text="start">b</p><p text="after">c</p></page>'
    )
    assert not f.matches(_make_block(2, 0, page2))
    assert f.matches(_make_block(2, 1, page2))
    assert f.matches(_make_block(2, 2, page2))
    assert f.matches(_make_block(3, 0, "<page><p>a</p></page>"))
    page4 = '<page><p text="end">a</p><p text="after">b</p></page>'
    assert f.matches(_make_block(4, 0, page4))
    assert not f.matches(_make_block(4, 1, page4))
    assert not f.matches(_make_block(5, 0, "<page><p>a</p></page>"))


def test_filter_matches__image_label_start_plain_end():
    f = s.Filter("(image 2:mid 4)")
    page2 = '<page><p text="before">a</p><p text="mid">b</p></page>'
    assert not f.matches(_make_block(2, 0, page2))
    assert f.matches(_make_block(2, 1, page2))
    assert f.matches(_make_block(4, 0, "<page><p>a</p></page>"))


def test_filter_matches__image_plain_start_label_end():
    f = s.Filter("(image 2 4:mid)")
    assert f.matches(_make_block(2, 0, "<page><p>a</p></page>"))
    page4 = '<page><p text="mid">a</p><p text="after">b</p></page>'
    assert f.matches(_make_block(4, 0, page4))
    assert not f.matches(_make_block(4, 1, page4))


def test_filter_matches__image_label_not_found():
    f = s.Filter("(image 3:nonexistent)")
    block = _make_block(3, 0, '<page><p text="other">a</p></page>')
    assert not f.matches(block)


def test_filter_matches__image_label_picks_first():
    f = s.Filter("(image 3:dup)")
    page = '<page><p text="dup">a</p><p text="dup">b</p><p>c</p></page>'
    assert f.matches(_make_block(3, 0, page))
    assert not f.matches(_make_block(3, 1, page))
    assert not f.matches(_make_block(3, 2, page))


# Filter sort key
# -------------------------------------------------------------------


def test_filter_sort_key__simple_image_orders_ascending():
    targets = ["(image 5)", "(image 1)", "(image 3)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1)",
        "(image 3)",
        "(image 5)",
    ]


def test_filter_sort_key__image_range_orders_by_start():
    targets = ["(image 5 10)", "(image 1 4)", "(image 11 20)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1 4)",
        "(image 5 10)",
        "(image 11 20)",
    ]


def test_filter_sort_key__page_alias_treated_as_unsortable():
    # Only `image` counts — `page` (and anything else) sorts last.
    targets = ["(page 1)", "(image 5)"]
    assert sorted(targets, key=s.filter_sort_key) == ["(image 5)", "(page 1)"]


def test_filter_sort_key__image_with_label_spec():
    targets = ["(image 5:foo)", "(image 1:bar 3:baz)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1:bar 3:baz)",
        "(image 5:foo)",
    ]


def test_filter_sort_key__nested_image_in_and():
    targets = ["(and (image 5) (tag p))", "(image 1)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1)",
        "(and (image 5) (tag p))",
    ]


def test_filter_sort_key__nested_image_in_or():
    targets = ["(or (image 5) (image 7))", "(image 1)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1)",
        "(or (image 5) (image 7))",
    ]


def test_filter_sort_key__nested_image_in_not():
    targets = ["(not (image 5))", "(image 1)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1)",
        "(not (image 5))",
    ]


def test_filter_sort_key__no_image_sorts_last():
    targets = ["(label foo)", "(image 1)", "(tag p)"]
    assert sorted(targets, key=s.filter_sort_key) == [
        "(image 1)",
        "(label foo)",
        "(tag p)",
    ]


def test_filter_sort_key__bare_label_sorts_last():
    targets = ["foo", "(image 1)"]
    assert sorted(targets, key=s.filter_sort_key) == ["(image 1)", "foo"]


def test_filter_sort_key__empty_target_sorts_last():
    targets = ["", "(image 1)", None]
    assert sorted(targets, key=s.filter_sort_key) == ["(image 1)", "", None]


def test_filter_sort_key__invalid_filter_sorts_last():
    targets = ["(image 1", "(image 1)"]
    assert sorted(targets, key=s.filter_sort_key) == ["(image 1)", "(image 1"]


def test_filter_sort_key__stable_for_equal_image_ranges():
    items = [
        ("a", "(image 1)"),
        ("b", "(image 1)"),
        ("c", "(image 1)"),
    ]
    sorted_items = sorted(items, key=lambda x: s.filter_sort_key(x[1]))
    assert [x[0] for x in sorted_items] == ["a", "b", "c"]


def test_filter_sort_key__stable_for_no_image_ranges():
    items = [
        ("a", "(label x)"),
        ("b", "(image 1)"),
        ("c", "(label y)"),
        ("d", "(image 2)"),
    ]
    sorted_items = sorted(items, key=lambda x: s.filter_sort_key(x[1]))
    assert [x[0] for x in sorted_items] == ["b", "d", "a", "c"]


def test_n_counter():
    ns = s.NCounter()

    # Basic usage
    assert ns.next("p") == "p1"
    assert ns.next("p") == "p2"
    assert ns.next("lg") == "lg1"

    # Override
    ns.override("p", "1.5")
    assert ns.next("p") == "1.6"
    assert ns.next("lg") == "lg2"

    # Override, non-numeric
    ns.override("head", "head")
    assert ns.next("head") == "head2"

    # Set prefix
    ns.set_prefix("2")
    assert ns.next("p") == "2.p1"
    assert ns.next("lg") == "2.lg1"


def test_n_counter__maybe_assign_n():
    ns = s.NCounter()

    note_xml = s._safe_fromstring("<note>a</note>")
    ns.maybe_assign_n("1", note_xml)
    assert "n" not in note_xml

    sp_xml = s._safe_fromstring("<sp>a</sp>")
    ns.maybe_assign_n("1", sp_xml)
    assert "n" not in sp_xml

    speaker_xml = s._safe_fromstring("<speaker>a</speaker>")
    ns.maybe_assign_n("1", speaker_xml)
    assert "n" not in speaker_xml

    p_xml = s._safe_fromstring("<p>a</p>")
    ns.maybe_assign_n("1", p_xml)
    assert p_xml.attrib["n"] == "1"

    p_xml_2 = s._safe_fromstring("<p>a</p>")
    ns.maybe_assign_n(None, p_xml_2)
    assert p_xml_2.attrib["n"] == "2"

    # TODO: maybe_assign_n with "sp"


# Block-level rewriting
# -------------------------------------------------------------------


def _assert_rewrite_block(input, expected):
    xml = etree.fromstring(input)
    s._rewrite_block_to_tei_xml(xml, 42)
    actual = s._to_string(xml)
    assert expected == actual


@pytest.mark.parametrize(
    "input,expected",
    [
        # `n` is preserved
        ('<p n="3">foo</p>', '<p n="3">foo</p>'),
        ('<verse n="3">foo</verse>', '<lg n="3"><l>foo</l></lg>'),
        ('<heading n="3">foo</heading>', '<head n="3">foo</head>'),
        ('<trailer n="3">foo</trailer>', '<trailer n="3">foo</trailer>'),
    ],
)
def test_rewrite_block_to_tei_xml__n_is_preserved(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Basic usage
        ("<p>foo</p>", "<p>foo</p>"),
        # <p> joins together text spread across multiple lines.
        ("<p>foo \nbar</p>", "<p>foo bar</p>"),
        ("<p>foo\nbar</p>", "<p>foo bar</p>"),
        ("<p>foo \n bar</p>", "<p>foo bar</p>"),
        # `-` at the end of a line joins words together across lines.
        ("<p>foo-\nbar</p>", "<p>foobar</p>"),
        ("<p>foo-bar\nbiz</p>", "<p>foo-bar biz</p>"),
        # <p> should respect and retain inline marks when joining text.
        ("<p><fix>foo</fix> \n bar</p>", "<p><supplied>foo</supplied> bar</p>"),
    ],
)
def test_rewrite_block_to_tei_xml__p(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Basic usage
        ("<verse>foo</verse>", "<lg><l>foo</l></lg>"),
        # <lg> breaks down lines (separated by whitespace) into separate <l> elements.
        ("<verse>foo\nbar</verse>", "<lg><l>foo</l><l>bar</l></lg>"),
        ("<verse>foo\nbar\nbiz</verse>", "<lg><l>foo</l><l>bar</l><l>biz</l></lg>"),
        # <lg> should respect and retain inline marks when splitting lines.
        (
            "<verse>f<fix>oo</fix>oo\nbar</verse>",
            "<lg><l>f<supplied>oo</supplied>oo</l><l>bar</l></lg>",
        ),
        # <lg> should respect and retain inline marks at the end of lines too.
        (
            "<verse>f<fix>oo</fix>\nbar</verse>",
            "<lg><l>f<supplied>oo</supplied></l><l>bar</l></lg>",
        ),
        # <lg> should normalize whitespace to some extent.
        (
            "<verse>f<fix>oo</fix> \n bar</verse>",
            "<lg><l>f<supplied>oo</supplied></l><l>bar</l></lg>",
        ),
    ],
)
def test_rewrite_block_to_tei_xml__verse(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<verse>a ॥ 1 ॥</verse>", "<lg><l>a ॥ 1 ॥</l></lg>"),
        ("<verse>a॥1॥</verse>", "<lg><l>a ॥ 1 ॥</l></lg>"),
        ("<verse>a ॥ 1   ॥  </verse>", "<lg><l>a ॥ 1 ॥</l></lg>"),
    ],
)
def test_rewrite_block_to_tei_xml__verse__normalize_double_dandas(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<heading>foo</heading>", "<head>foo</head>"),
        # Whitespace
        ("<heading>  foo </heading>", "<head>foo</head>"),
        # Whitespace with child elements
        ("<heading>  foo <b>bar</b> </heading>", "<head>foo <b>bar</b></head>"),
    ],
)
def test_rewrite_block_to_tei_xml__heading(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<title>foo</title>", "<title>foo</title>"),
        # Whitespace
        ("<title> foo </title>", "<title>foo</title>"),
        # Whitespace with child elements
        ("<title>  foo <b>bar</b> </title>", "<title>foo <b>bar</b></title>"),
    ],
)
def test_rewrite_block_to_tei_xml__title(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<subtitle>foo</subtitle>", '<title type="sub">foo</title>'),
        # Whitespace
        ("<subtitle> foo </subtitle>", '<title type="sub">foo</title>'),
        # Whitespace with child elements
        (
            "<subtitle>  foo <b>bar</b> </subtitle>",
            '<title type="sub">foo <b>bar</b></title>',
        ),
    ],
)
def test_rewrite_block_to_tei_xml__subtitle(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<trailer>foo</trailer>", "<trailer>foo</trailer>"),
        # Whitespace
        ("<trailer> foo </trailer>", "<trailer>foo</trailer>"),
        # Whitespace with child elements
        ("<trailer>  foo <b>bar</b> </trailer>", "<trailer>foo <b>bar</b></trailer>"),
    ],
)
def test_rewrite_block_to_tei_xml__trailer(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("<footnote>foo</footnote>", '<note type="footnote">foo</note>'),
        # TODO: first token "1", "(ka)", etc.
    ],
)
def test_rewrite_block_to_tei_xml__trailer(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # <speaker> converts the block type to <sp>. <speaker> is yanked out of the block into <sp>,
        # preserving element order. The old block type is appended as a child to <sp>.
        ("<p><speaker>foo</speaker></p>", "<sp><speaker>foo</speaker></sp>"),
        (
            "<p><speaker>foo</speaker>bar-\nbiz</p>",
            "<sp><speaker>foo</speaker><p>barbiz</p></sp>",
        ),
        # Speaker without content
        ("<p><speaker>foo</speaker></p>", "<sp><speaker>foo</speaker></sp>"),
        # Speaker without content + with whitespace
        ("<p> <speaker>foo</speaker> </p>", "<sp><speaker>foo</speaker></sp>"),
        # Speaker with <p> content
        (
            "<p><speaker>foo</speaker> bar</p>",
            "<sp><speaker>foo</speaker><p>bar</p></sp>",
        ),
        # Speaker with <lg> content
        (
            "<verse><speaker>foo</speaker> bar</verse>",
            "<sp><speaker>foo</speaker><lg><l>bar</l></lg></sp>",
        ),
    ],
)
def test_rewrite_block_to_tei_xml__tei_sp(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Default
        ("<p><stage>foo</stage></p>", "<p><stage>foo</stage></p>"),
        # Whitespace is stripped
        ("<p><stage> foo </stage></p>", "<p><stage>foo</stage></p>"),
        # Parens moved to `rend`
        ("<p><stage>(foo)</stage></p>", '<p><stage rend="parentheses">foo</stage></p>'),
        # Parens moved to `rend` + whitespace
        (
            "<p><stage> ( foo ) </stage></p>",
            '<p><stage rend="parentheses">foo</stage></p>',
        ),
        # Space is inserted before a following element
        ("<p><stage>foo</stage>bar</p>", "<p><stage>foo</stage> bar</p>"),
    ],
)
def test_rewrite_block_to_tei_xml__stage(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Default
        ("<p><speaker>foo</speaker></p>", "<sp><speaker>foo</speaker></sp>"),
        # Dashes are stripped
        (
            "<p><speaker>foo - </speaker></p>",
            '<sp><speaker rend="dash">foo</speaker></sp>',
        ),
        # Dashes and whitespace are stripped
        (
            "<p><speaker> foo -– </speaker></p>",
            '<sp><speaker rend="dash">foo</speaker></sp>',
        ),
    ],
)
def test_rewrite_block_to_tei_xml__speaker(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Default case
        (
            "<p>aoeu<chaya>asdf</chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra">aoeu</seg><seg xml:lang="sa">asdf</seg></choice></p>',
        ),
        # Child elements are moved properly
        (
            "<p>aoeu<x>foo</x><chaya>asdf<y>bar</y></chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra">aoeu<x>foo</x></seg><seg xml:lang="sa">asdf<y>bar</y></seg></choice></p>',
        ),
        # rend - no brackets
        (
            "<p><chaya>foo</chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra" /><seg xml:lang="sa">foo</seg></choice></p>',
        ),
        # rend - whitespace
        (
            "<p><chaya> foo </chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra" /><seg xml:lang="sa">foo</seg></choice></p>',
        ),
        # rend - brackets
        (
            "<p><chaya>[foo]</chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra" /><seg xml:lang="sa" rend="brackets">foo</seg></choice></p>',
        ),
        # rend - brackets and whitespace
        (
            "<p><chaya> [ foo ] </chaya></p>",
            '<p><choice type="chaya"><seg xml:lang="pra" /><seg xml:lang="sa" rend="brackets">foo</seg></choice></p>',
        ),
    ],
)
def test_rewrite_block_to_tei_xml__chaya(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # TODO: too hard
        # ("<verse>f<fix>oo\nbar</fix> biz</verse>", "<lg><l>f<supplied>oo</supplied></l><l><supplied>bar</supplied> biz</l></lg>"),
        # <error> and <fix>
        # Error and fix consecutively (despite whitespace) --> sic and corr
        (
            "<p>foo<error>bar</error> <fix>biz</fix> tail</p>",
            "<p>foo<choice><sic>bar</sic><corr>biz</corr></choice> tail</p>",
        ),
        # Invariant to order.
        (
            "<p>foo<fix>biz</fix> <error>bar</error></p>",
            "<p>foo<choice><sic>bar</sic><corr>biz</corr></choice></p>",
        ),
        # Error alone --> sic, with empty corr
        (
            "<p>foo<error>bar</error> tail</p>",
            "<p>foo<choice><sic>bar</sic><corr /></choice> tail</p>",
        ),
        # Fix alone --> supplied (no corr)
        ("<p>foo<fix>bar</fix></p>", "<p>foo<supplied>bar</supplied></p>"),
        # Separate fix and error -- don't group into a single choice
        (
            "<p>foo<error>bar</error> biz <fix>baf</fix> tail</p>",
            "<p>foo<choice><sic>bar</sic><corr /></choice> biz <supplied>baf</supplied> tail</p>",
        ),
    ],
)
def test_rewrite_block_to_tei_xml__error_and_fix(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # <flag> --> <unclear>
        ("<p><flag>foo</flag></p>", "<p><unclear>foo</unclear></p>"),
    ],
)
def test_rewrite_block_to_tei_xml__flag(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # <delete> and <add> consecutively --> <subst><del>...<add>...</subst>
        (
            "<p>foo<delete>bar</delete> <add>biz</add> tail</p>",
            "<p>foo<subst><del>bar</del><add>biz</add></subst> tail</p>",
        ),
        # Invariant to order.
        (
            "<p>foo<add>biz</add> <delete>bar</delete></p>",
            "<p>foo<subst><del>bar</del><add>biz</add></subst></p>",
        ),
        # Delete alone --> <del>
        (
            "<p>foo<delete>bar</delete> tail</p>",
            "<p>foo<del>bar</del> tail</p>",
        ),
        # Add alone --> <add> (unchanged)
        (
            "<p>foo<add>bar</add> tail</p>",
            "<p>foo<add>bar</add> tail</p>",
        ),
        # Separate add and delete -- don't group into a single subst
        (
            "<p>foo<delete>bar</delete> biz <add>baf</add> tail</p>",
            "<p>foo<del>bar</del> biz <add>baf</add> tail</p>",
        ),
    ],
)
def test_rewrite_block_to_tei_xml__delete_and_add(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        # Bracketed <add> text --> rend="brackets"
        (
            "<p>foo<add>[bar]</add>baz</p>",
            '<p>foo<add rend="brackets">bar</add>baz</p>',
        ),
        # Non-bracketed <add> text --> no rend
        (
            "<p>foo<add>bar</add>baz</p>",
            "<p>foo<add>bar</add>baz</p>",
        ),
        # Bracketed with whitespace
        (
            "<p>foo<add>[ bar ]</add>baz</p>",
            '<p>foo<add rend="brackets">bar</add>baz</p>',
        ),
    ],
)
def test_rewrite_block_to_tei_xml__add_brackets(input, expected):
    _assert_rewrite_block(input, expected)


@pytest.mark.parametrize(
    "first,second,expected",
    [
        # Simple <p>
        ("<p>foo</p>", "<p>bar</p>", '<p>foo<pb n="42" />bar</p>'),
        # Simple <lg>
        (
            "<lg><l>foo</l></lg>",
            "<lg><l>bar</l></lg>",
            '<lg><l>foo</l><pb n="42" /><l>bar</l></lg>',
        ),
        # <p> with children
        (
            "<p>foo <a>A</a></p>",
            "<p>bar <b>B</b></p>",
            '<p>foo <a>A</a><pb n="42" />bar <b>B</b></p>',
        ),
        # <lg> with children
        (
            "<lg><l>foo <a>A</a></l></lg>",
            "<lg><l>bar <b>B</b></l></lg>",
            '<lg><l>foo <a>A</a></l><pb n="42" /><l>bar <b>B</b></l></lg>',
        ),
        # Simple <sp> with child <p>
        (
            "<sp><speaker>hi</speaker><p>foo</p></sp>",
            "<p>bar</p>",
            '<sp><speaker>hi</speaker><p>foo<pb n="42" />bar</p></sp>',
        ),
        # Simple <sp> with child <lg>
        (
            "<sp><speaker>hi</speaker><lg><l>foo</l></lg></sp>",
            "<lg><l>bar</l></lg>",
            '<sp><speaker>hi</speaker><lg><l>foo</l><pb n="42" /><l>bar</l></lg></sp>',
        ),
        # Simple <sp> with multiple child <p> -- append to latest
        (
            "<sp><speaker>hi</speaker><p>blah</p><p>foo</p></sp>",
            "<p>bar</p>",
            '<sp><speaker>hi</speaker><p>blah</p><p>foo<pb n="42" />bar</p></sp>',
        ),
    ],
)
def test_concatenate_tei_xml_blocks_across_page_boundary(first, second, expected):
    _first = etree.fromstring(first)
    _second = etree.fromstring(second)

    actual = s._concatenate_tei_xml_blocks_across_page_boundary(_first, _second, "42")
    actual = s._to_string(_first)
    assert expected == actual


# Block splitting at <break/>
# -------------------------------------------------------------------


@pytest.mark.parametrize(
    "input,expected",
    [
        # No break -> single element, unchanged
        ("<p>foo</p>", ["<p>foo</p>"]),
        # Single break in <p> -> two <p> elements
        ("<p>foo<break/>bar</p>", ["<p>foo</p>", "<p>bar</p>"]),
        # Single break in <verse> -> two <verse> elements
        ("<verse>foo<break/>bar</verse>", ["<verse>foo</verse>", "<verse>bar</verse>"]),
        # Multiple breaks -> N+1 elements
        (
            "<p>a<break/>b<break/>c</p>",
            ["<p>a</p>", "<p>b</p>", "<p>c</p>"],
        ),
        # Break with inline marks preserved on correct side
        (
            "<p>foo<fix>bar</fix><break/>biz</p>",
            ["<p>foo<fix>bar</fix></p>", "<p>biz</p>"],
        ),
        # Break with inline marks after break
        (
            "<p>foo<break/><fix>bar</fix>biz</p>",
            ["<p>foo</p>", "<p><fix>bar</fix>biz</p>"],
        ),
        # Attributes (except n) are copied to sub-blocks
        (
            '<p n="1" lang="sa">foo<break/>bar</p>',
            ['<p n="1" lang="sa">foo</p>', '<p lang="sa">bar</p>'],
        ),
    ],
)
def test_split_block_at_breaks(input, expected):
    xml = etree.fromstring(input)
    result = s._split_block_at_breaks(xml)
    actual = [s._to_string(el) for el in result]
    assert actual == expected


# Publishing with <break/>
# -------------------------------------------------------------------


def test_create_tei_document__break_in_paragraph():
    _test_create_tei_document(
        ["<page><p>foo<break/>bar</p></page>"],
        [
            s.TEIBlock(xml='<p n="p1">foo</p>', slug="p1", page_id=0),
            s.TEIBlock(xml='<p n="p2">bar</p>', slug="p2", page_id=0),
        ],
    )


def test_create_tei_document__break_in_verse():
    _test_create_tei_document(
        ["<page><verse>line1\nline2<break/>line3\nline4</verse></page>"],
        [
            s.TEIBlock(
                xml='<lg n="1"><l>line1</l><l>line2</l></lg>',
                slug="1",
                page_id=0,
            ),
            s.TEIBlock(
                xml='<lg n="2"><l>line3</l><l>line4</l></lg>',
                slug="2",
                page_id=0,
            ),
        ],
    )


def test_create_tei_document__multiple_breaks():
    _test_create_tei_document(
        ["<page><p>a<break/>b<break/>c</p></page>"],
        [
            s.TEIBlock(xml='<p n="p1">a</p>', slug="p1", page_id=0),
            s.TEIBlock(xml='<p n="p2">b</p>', slug="p2", page_id=0),
            s.TEIBlock(xml='<p n="p3">c</p>', slug="p3", page_id=0),
        ],
    )


def test_create_tei_document__no_break_backward_compatible():
    """Blocks without <break/> should produce identical output to before."""
    _test_create_tei_document(
        ["<page><p>foo</p></page>"],
        [s.TEIBlock(xml='<p n="p1">foo</p>', slug="p1", page_id=0)],
    )


# Doc-level rewriting
# -------------------------------------------------------------------


def _test_create_tei_document(input, expected):
    """Helper function for testing create_tei_document."""
    page_status = db.PageStatus(name=SitePageStatus.R1)

    pages = []
    revisions = []
    for i, page_xml in enumerate(input):
        revision = db.Revision(id=i, page_id=i, content=page_xml, status=page_status)
        revisions.append(revision)
        pages.append(
            db.Page(id=i, slug=str(i), order=i, status_id=1, revisions=[revision])
        )

    project = db.Project(
        slug="test", display_title="Test", page_numbers="", pages=pages
    )
    text = db.Text(slug="test", title="Test", language="sa", stage="public")
    config = db.PublishConfig(target="(and)", text=text)

    conversion = s.create_tei_document(project, config, revisions=revisions)
    assert conversion.items == expected


@pytest.mark.parametrize(
    "input,expected",
    [
        # Single <head>
        (
            ["<page><head>foo</head></page>"],
            [s.TEIBlock(xml='<head n="head">foo</head>', slug="head", page_id=0)],
        ),
        # Single <trailer>
        (
            ["<page><trailer>foo</trailer></page>"],
            [
                s.TEIBlock(
                    xml='<trailer n="trailer">foo</trailer>', slug="trailer", page_id=0
                )
            ],
        ),
        # Single <title>
        (
            ["<page><title>foo</title></page>"],
            [s.TEIBlock(xml='<title n="title">foo</title>', slug="title", page_id=0)],
        ),
        # Single subtitle
        (
            ["<page><subtitle>foo</subtitle></page>"],
            [
                s.TEIBlock(
                    xml='<title type="sub" n="subtitle">foo</title>',
                    slug="subtitle",
                    page_id=0,
                )
            ],
        ),
        # Multiple subtitles
        (
            ["<page><subtitle>foo</subtitle><subtitle>bar</subtitle></page>"],
            [
                s.TEIBlock(
                    xml='<title type="sub" n="subtitle1">foo</title>',
                    slug="subtitle1",
                    page_id=0,
                ),
                s.TEIBlock(
                    xml='<title type="sub" n="subtitle2">bar</title>',
                    slug="subtitle2",
                    page_id=0,
                ),
            ],
        ),
        # Single <title> with subtitle
        (
            ["<page><title>foo</title><subtitle>bar</subtitle></page>"],
            [
                s.TEIBlock(xml='<title n="title">foo</title>', slug="title", page_id=0),
                s.TEIBlock(
                    xml='<title type="sub" n="subtitle">bar</title>',
                    slug="subtitle",
                    page_id=0,
                ),
            ],
        ),
        # Multiple <head>
        (
            ["<page><head>foo</head><head>bar</head></page>"],
            [
                s.TEIBlock(xml='<head n="head1">foo</head>', slug="head1", page_id=0),
                s.TEIBlock(xml='<head n="head2">bar</head>', slug="head2", page_id=0),
            ],
        ),
        # Multiple <trailer>
        (
            ["<page><trailer>foo</trailer><trailer>bar</trailer></page>"],
            [
                s.TEIBlock(
                    xml='<trailer n="trailer1">foo</trailer>',
                    slug="trailer1",
                    page_id=0,
                ),
                s.TEIBlock(
                    xml='<trailer n="trailer2">bar</trailer>',
                    slug="trailer2",
                    page_id=0,
                ),
            ],
        ),
    ],
)
def test_create_tei_document__rewrite_head_trailer(input, expected):
    _test_create_tei_document(input, expected)


@pytest.mark.parametrize(
    "input,expected",
    [
        (
            ["<page><verse>a</verse><verse>b</verse></page>"],
            [
                s.TEIBlock(xml="<lg><l>a</l></lg>", slug="1", page_id=0),
                s.TEIBlock(xml="<lg><l>b</l></lg>", slug="2", page_id=0),
            ],
        ),
        (
            [
                "<page><metadata>div.n = 1</metadata><verse>a</verse><verse>b</verse></page>"
            ],
            [
                s.TEIBlock(xml="<lg><l>a</l></lg>", slug="1.1", page_id=0),
                s.TEIBlock(xml="<lg><l>b</l></lg>", slug="1.2", page_id=0),
            ],
        ),
    ],
)
def _test_create_tei_document__rewrite_lg_n_attrib(input, expected):
    _test_create_tei_document(input, expected)


def test_create_tei_document__page_order_differs_from_page_id():
    """image_number must follow Page.order, not Page.id.

    Pages:
      page_id=10, order=2  (visual position 3) -> content "a"
      page_id=20, order=0  (visual position 1) -> content "b"
      page_id=30, order=1  (visual position 2) -> content "c"

    Revisions are passed in page_id order (simulating the old query).
    Filter selects image 1, which should be page_id=20 ("b", order=0).

    Before the fix, enumerate gave r(pid=10) image_number=1, selecting "a".
    """
    page_status = db.PageStatus(name=SitePageStatus.R1)

    r0 = db.Revision(
        id=0, page_id=10, content='<page><p n="1">a</p></page>', status=page_status
    )
    r1 = db.Revision(
        id=1, page_id=20, content='<page><p n="2">b</p></page>', status=page_status
    )
    r2 = db.Revision(
        id=2, page_id=30, content='<page><p n="3">c</p></page>', status=page_status
    )

    pages = [
        db.Page(id=20, slug="2", order=0, status_id=1, revisions=[r1]),
        db.Page(id=30, slug="3", order=1, status_id=1, revisions=[r2]),
        db.Page(id=10, slug="1", order=2, status_id=1, revisions=[r0]),
    ]

    project = db.Project(
        slug="test", display_title="Test", page_numbers="", pages=pages
    )
    # Select image 1 = visual position 1 = page_id=20 (order=0) = "b"
    text = db.Text(slug="test", title="Test", language="sa", stage="public")
    config = db.PublishConfig(target="(image 1)", text=text)

    conversion = s.create_tei_document(
        project,
        config,
        revisions=[r0, r1, r2],  # page_id order (old query)
    )
    assert conversion.items == [
        s.TEIBlock(xml='<p n="2">b</p>', slug="2", page_id=20),
    ]


def test_create_tei_document__pages_without_revisions_do_not_shift_image_numbers():
    """Pages with no revisions must not shift image numbers for later pages.

    3 pages in visual order, but only pages 1 and 3 have revisions.
    Page 2 (image 2) has no revision and should be skipped without
    shifting page 3 from image 3 to image 2.
    """
    page_status = db.PageStatus(name=SitePageStatus.R1)

    r0 = db.Revision(
        id=0, page_id=0, content='<page><p n="1">a</p></page>', status=page_status
    )
    r2 = db.Revision(
        id=2, page_id=2, content='<page><p n="2">c</p></page>', status=page_status
    )

    pages = [
        db.Page(id=0, slug="1", order=0, status_id=1, revisions=[r0]),
        db.Page(id=1, slug="2", order=1, status_id=1, revisions=[]),  # no revision
        db.Page(id=2, slug="3", order=2, status_id=1, revisions=[r2]),
    ]

    project = db.Project(
        slug="test", display_title="Test", page_numbers="", pages=pages
    )
    # Select only image 3 — should match page_id=2 ("c"), not be shifted to image 2.
    text = db.Text(slug="test", title="Test", language="sa", stage="public")
    config = db.PublishConfig(target="(image 3)", text=text)

    conversion = s.create_tei_document(project, config, revisions=[r0, r2])
    assert conversion.items == [
        s.TEIBlock(xml='<p n="2">c</p>', slug="2", page_id=2),
    ]


def test_create_tei_document__paragraph():
    _test_create_tei_document(
        ['<page><p n="1">अ</p></page>'],
        [s.TEIBlock(xml='<p n="1">अ</p>', slug="1", page_id=0)],
    )


def test_create_tei_document__paragraph_with_concatenation():
    _test_create_tei_document(
        [
            '<page><p n="1" merge-next="true">अ</p></page>',
            '<page><p n="1">a</p></page>',
        ],
        [s.TEIBlock(xml='<p n="1">अ<pb n="2" />a</p>', slug="1", page_id=0)],
    )


def test_create_tei_document__paragraph_with_multiple_concatenation():
    _test_create_tei_document(
        [
            '<page><p merge-next="true">a</p></page>',
            '<page><p merge-next="true">b</p></page>',
            '<page><p merge-next="true">c</p></page>',
            "<page><p>d</p></page>",
        ],
        [
            s.TEIBlock(
                xml='<p n="p1">a<pb n="2" />b<pb n="3" />c<pb n="4" />d</p>',
                slug="p1",
                page_id=0,
            )
        ],
    )


def test_create_tei_document__paragraph_with_speaker():
    _test_create_tei_document(
        ['<page><p n="1"><speaker>foo</speaker> अ</p></page>'],
        [
            s.TEIBlock(
                xml='<sp n="sp1"><speaker>foo</speaker><p n="1">अ</p></sp>',
                slug="sp1",
                page_id=0,
            )
        ],
    )


def test_create_tei_document__paragraph_with_speaker_and_concatenation():
    _test_create_tei_document(
        [
            '<page><p n="1" merge-next="true"><speaker>foo</speaker> अ</p></page>',
            '<page><p n="1">a</p></page>',
        ],
        [
            s.TEIBlock(
                xml='<sp n="sp1"><speaker>foo</speaker><p n="1">अ<pb n="2" />a</p></sp>',
                slug="sp1",
                page_id=0,
            ),
        ],
    )


def test_create_tei_document__verse():
    _test_create_tei_document(
        ['<page><verse n="1">अ</verse></page>'],
        [s.TEIBlock(xml='<lg n="1"><l>अ</l></lg>', slug="1", page_id=0)],
    )


def test_create_tei_document__verse_with_concatenation():
    _test_create_tei_document(
        [
            '<page><verse n="1" merge-next="true">अ</verse></page>',
            '<page><verse n="1">a</verse></page>',
        ],
        [
            s.TEIBlock(
                xml='<lg n="1"><l>अ</l><pb n="2" /><l>a</l></lg>', slug="1", page_id=0
            )
        ],
    )


def test_create_tei_document__verse_with_fix_inline_element():
    _test_create_tei_document(
        ['<page><verse n="1">अ<fix>क</fix>ख</verse></page>'],
        [
            s.TEIBlock(
                xml='<lg n="1"><l>अ<supplied>क</supplied>ख</l></lg>',
                slug="1",
                page_id=0,
            )
        ],
    )


def test_create_tei_document__paragraph_with_fix_inline_element():
    _test_create_tei_document(
        ['<page><p n="1">अ<fix>क</fix>ख</p></page>'],
        [
            s.TEIBlock(
                xml='<p n="1">अ<supplied>क</supplied>ख</p>', slug="1", page_id=0
            ),
        ],
    )


def test_create_tei_document__autoincrement():
    _test_create_tei_document(
        ['<page><p n="1">a</p><p>b</p><p>c</p></page>'],
        [
            s.TEIBlock(xml='<p n="1">a</p>', slug="1", page_id=0),
            s.TEIBlock(xml='<p n="2">b</p>', slug="2", page_id=0),
            s.TEIBlock(xml='<p n="3">c</p>', slug="3", page_id=0),
        ],
    )


def test_create_tei_document__autoincrement_with_div_n():
    _test_create_tei_document(
        ["<page><metadata>div.n=1</metadata><p>a</p><p>b</p><p>c</p></page>"],
        [
            s.TEISection(
                slug="1",
                blocks=[
                    s.TEIBlock(xml='<p n="1.p1">a</p>', slug="1.p1", page_id=0),
                    s.TEIBlock(xml='<p n="1.p2">b</p>', slug="1.p2", page_id=0),
                    s.TEIBlock(xml='<p n="1.p3">c</p>', slug="1.p3", page_id=0),
                ],
            )
        ],
    )


def test_create_tei_document__autoincrement_with_dot_prefix():
    _test_create_tei_document(
        ['<page><p n="1.1">a</p><p>b</p><p>c</p></page>'],
        [
            s.TEIBlock(xml='<p n="1.1">a</p>', slug="1.1", page_id=0),
            s.TEIBlock(xml='<p n="1.2">b</p>', slug="1.2", page_id=0),
            s.TEIBlock(xml='<p n="1.3">c</p>', slug="1.3", page_id=0),
        ],
    )


def test_create_tei_document__autoincrement_with_non_dot_prefix():
    _test_create_tei_document(
        ['<page><p n="p1">a</p><p>b</p><p>c</p></page>'],
        [
            s.TEIBlock(xml='<p n="p1">a</p>', slug="p1", page_id=0),
            s.TEIBlock(xml='<p n="p2">b</p>', slug="p2", page_id=0),
            s.TEIBlock(xml='<p n="p3">c</p>', slug="p3", page_id=0),
        ],
    )


def test_create_tei_document__autoincrement_with_weird_prefix():
    _test_create_tei_document(
        ['<page><p n="foo">a</p><p>b</p><p>c</p></page>'],
        [
            s.TEIBlock(xml='<p n="foo">a</p>', slug="foo", page_id=0),
            s.TEIBlock(xml='<p n="foo2">b</p>', slug="foo2", page_id=0),
            s.TEIBlock(xml='<p n="foo3">c</p>', slug="foo3", page_id=0),
        ],
    )


def test_create_tei_document__autoincrement_with_mixed_types():
    _test_create_tei_document(
        [
            '<page><p n="p1">a</p><verse n="1">A</verse></page>',
            "<page><p>b</p><verse>B</verse><p>c</p></page>",
        ],
        [
            s.TEIBlock(xml='<p n="p1">a</p>', slug="p1", page_id=0),
            s.TEIBlock(xml='<lg n="1"><l>A</l></lg>', slug="1", page_id=0),
            s.TEIBlock(xml='<p n="p2">b</p>', slug="p2", page_id=1),
            s.TEIBlock(xml='<lg n="2"><l>B</l></lg>', slug="2", page_id=1),
            s.TEIBlock(xml='<p n="p3">c</p>', slug="p3", page_id=1),
        ],
    )
