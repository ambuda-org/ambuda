"""Unit tests for plain-text export conversion."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock
from xml.etree import ElementTree as ET

import pytest

from ambuda.utils.text_exports import _simplify_tei_for_export, create_plain_text


def _simplify(xml_str: str) -> str:
    """Apply _simplify_tei_for_export and return the resulting XML string."""
    xml = ET.fromstring(xml_str)
    _simplify_tei_for_export(xml)
    return ET.tostring(xml, encoding="unicode")


# -- _simplify_tei_for_export tests --


def test_simplify__choice_keeps_corr_drops_sic():
    assert _simplify("<p>aaa<choice><sic>x</sic><corr>y</corr></choice>bbb</p>") == (
        "<p>aaa<choice><corr>y</corr></choice>bbb</p>"
    )


def test_simplify__choice_sic_only():
    assert _simplify("<p>aaa<choice><sic>x</sic></choice>bbb</p>") == ("<p>aaabbb</p>")


def test_simplify__choice_corr_only():
    assert _simplify("<p>aaa<choice><corr>y</corr></choice>bbb</p>") == (
        "<p>aaa<choice><corr>y</corr></choice>bbb</p>"
    )


def test_simplify__subst_keeps_add_drops_del():
    assert _simplify("<p>aaa<subst><del>x</del><add>y</add></subst>bbb</p>") == (
        "<p>aaa<subst><add>y</add></subst>bbb</p>"
    )


def test_simplify__subst_del_only():
    assert _simplify("<p>aaa<subst><del>x</del></subst>bbb</p>") == ("<p>aaabbb</p>")


def test_simplify__subst_add_only():
    assert _simplify("<p>aaa<subst><add>y</add></subst>bbb</p>") == (
        "<p>aaa<subst><add>y</add></subst>bbb</p>"
    )


def test_simplify__lone_del_removed():
    assert _simplify("<p>aaa<del>x</del>bbb</p>") == "<p>aaabbb</p>"


def test_simplify__lone_del_preserves_tail():
    assert _simplify("<p><del>x</del> tail</p>") == "<p> tail</p>"


def test_simplify__lone_del_after_sibling():
    """Tail text is appended to preceding sibling's tail."""
    assert _simplify("<p><b>aaa</b><del>x</del>bbb</p>") == "<p><b>aaa</b>bbb</p>"


def test_simplify__multiple_del_elements():
    assert _simplify("<p>a<del>1</del>b<del>2</del>c</p>") == "<p>abc</p>"


def test_simplify__no_special_elements():
    """Unrelated elements pass through unchanged."""
    assert _simplify("<p>aaa<b>bbb</b>ccc</p>") == "<p>aaa<b>bbb</b>ccc</p>"


def test_simplify__namespaced_choice():
    ns = "http://www.tei-c.org/ns/1.0"
    xml_str = f'<p xmlns="{ns}">aaa<choice><sic>x</sic><corr>y</corr></choice>bbb</p>'
    xml = ET.fromstring(xml_str)
    _simplify_tei_for_export(xml)
    result = ET.tostring(xml, encoding="unicode")
    assert "sic" not in result
    assert "y" in result


def test_simplify__namespaced_del():
    ns = "http://www.tei-c.org/ns/1.0"
    xml_str = f'<p xmlns="{ns}">aaa<del>x</del>bbb</p>'
    xml = ET.fromstring(xml_str)
    _simplify_tei_for_export(xml)
    result = ET.tostring(xml, encoding="unicode")
    assert "del" not in result
    assert "aaabbb" in result


def test_simplify__namespaced_subst():
    ns = "http://www.tei-c.org/ns/1.0"
    xml_str = f'<p xmlns="{ns}">aaa<subst><del>x</del><add>y</add></subst>bbb</p>'
    xml = ET.fromstring(xml_str)
    _simplify_tei_for_export(xml)
    result = ET.tostring(xml, encoding="unicode")
    assert "del" not in result
    assert "y" in result


# -- create_plain_text integration tests --


def _make_text(title="Test", slug="test", language="sa"):
    t = MagicMock()
    t.title = title
    t.slug = slug
    t.language = language
    return t


def _write_xml(tmp_path: Path, body_xml: str, header_xml: str = "<fileDesc/>") -> Path:
    """Write a minimal TEI XML file and return its path."""
    xml_path = tmp_path / "test.xml"
    xml_path.write_text(
        f"""<?xml version='1.0' encoding='utf-8'?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>{header_xml}</teiHeader>
  <text xml:id="test" xml:lang="sa">
    <body>
      {body_xml}
    </body>
  </text>
</TEI>""",
        encoding="utf-8",
    )
    return xml_path


def _header_lines(out_path: Path) -> list[str]:
    """Return all leading '# key: value' header lines."""
    result = []
    for line in out_path.read_text().splitlines():
        if line.startswith("# ") and ": " in line:
            result.append(line)
        elif line == "#":
            result.append(line)
        else:
            break
    return result


def _content_lines(out_path: Path) -> list[str]:
    """Return lines after the header block."""
    lines = out_path.read_text().splitlines()
    # Skip header lines (start with "# " with ": " or bare "#")
    idx = 0
    for idx, line in enumerate(lines):
        if line.startswith("# ") and ": " in line:
            continue
        if line == "#":
            continue
        break
    result = lines[idx:]
    # Strip trailing blank lines
    while result and result[-1] == "":
        result.pop()
    return result


def test_lg_no_leading_whitespace(tmp_path):
    """Lines inside <lg> should not have leading whitespace from XML indentation."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <lg n="1.1">
          <l>aaa bbb ccc</l>
          <l>ddd eee fff</l>
        </lg>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# 1.1",
        "aaa bbb ccc",
        "ddd eee fff",
    ]


def test_choice_uses_corr_not_sic(tmp_path):
    """<choice> should use <corr> and drop <sic>, with no extra whitespace."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <trailer n="trailer">aaa<choice>
              <sic>x</sic>
              <corr>y</corr>
            </choice>bbb</trailer>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# trailer",
        "aaaybbb",
    ]


def test_block_slug_heading(tmp_path):
    """Each block should be preceded by '# <slug>'."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <lg n="1.1">
          <l>aaa</l>
          <l>bbb</l>
        </lg>
        <lg n="1.2">
          <l>ccc</l>
          <l>ddd</l>
        </lg>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# 1.1",
        "aaa",
        "bbb",
        "",
        "# 1.2",
        "ccc",
        "ddd",
    ]


def test_div_sections_not_emitted(tmp_path):
    """<div> section containers should not produce empty blocks."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <div n="4">
          <lg n="4.1">
            <l>aaa</l>
          </lg>
        </div>
        <div n="5">
          <lg n="5.1">
            <l>bbb</l>
          </lg>
        </div>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# 4.1",
        "aaa",
        "",
        "# 5.1",
        "bbb",
    ]


def test_header_minimal(tmp_path):
    """With a bare teiHeader, header has title, slug, and export fields."""
    xml_path = _write_xml(
        tmp_path,
        '<p n="1">hello</p>',
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text("Test"), out_path, xml_path)

    header = _header_lines(out_path)
    assert "# title: Test" in header
    assert "# slug: test" in header
    assert "# exported_from: ambuda.org" in header
    # exported_on should be a date
    exported_on = [l for l in header if l.startswith("# exported_on:")]
    assert len(exported_on) == 1


def test_header_rich_metadata(tmp_path):
    """Header extracts title, author, license, source, and credits from TEI."""
    header_xml = textwrap.dedent("""\
        <fileDesc>
          <titleStmt>
            <title>My Title</title>
            <author>Some Author</author>
            <respStmt>
              <resp>data entry</resp>
              <name>Alice</name>
            </respStmt>
            <respStmt>
              <resp>proofreading</resp>
              <name>Bob</name>
            </respStmt>
          </titleStmt>
          <publicationStmt>
            <availability>
              <licence>CC BY 4.0</licence>
            </availability>
          </publicationStmt>
          <notesStmt>
            <note>A useful note.</note>
          </notesStmt>
          <sourceDesc>
            <bibl>
              <title>Source Book</title>
              <author>Src Author</author>
              <editor>Src Editor</editor>
              <publisher>Src Press</publisher>
              <pubPlace>Src City</pubPlace>
              <date>1900</date>
            </bibl>
          </sourceDesc>
        </fileDesc>""")
    xml_path = _write_xml(
        tmp_path,
        '<p n="1">hello</p>',
        header_xml=header_xml,
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text("My Title"), out_path, xml_path)

    header = _header_lines(out_path)
    assert "# title: My Title" in header
    assert "# author: Some Author" in header
    assert "# license: CC BY 4.0" in header
    assert "#" in header  # separator between groups
    assert "# source_title: Source Book" in header
    assert "# source_author: Src Author" in header
    assert "# source_editor: Src Editor" in header
    assert "# source_publisher: Src Press" in header
    assert "# source_publisher_place: Src City" in header
    assert "# source_year: 1900" in header
    assert "#" in header
    assert "# credits: Alice (data entry), Bob (proofreading)" in header
    assert "# notes: A useful note." in header


def test_header_omits_empty_fields(tmp_path):
    """Fields with no data are omitted from the header."""
    header_xml = textwrap.dedent("""\
        <fileDesc>
          <titleStmt>
            <title>Minimal</title>
          </titleStmt>
          <publicationStmt/>
          <sourceDesc><bibl/></sourceDesc>
        </fileDesc>""")
    xml_path = _write_xml(
        tmp_path,
        '<p n="1">hello</p>',
        header_xml=header_xml,
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text("Minimal"), out_path, xml_path)

    header = _header_lines(out_path)
    header_text = "\n".join(header)
    assert "source_" not in header_text
    assert "credits" not in header_text
    assert "notes" not in header_text
    # But title and export fields are always present
    assert "# title: Minimal" in header
    assert "# exported_from: ambuda.org" in header


def test_sp_speaker_on_own_line(tmp_path):
    """<speaker> inside <sp> should appear on its own line with em dash."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <sp n="sp1">
          <speaker>Alice</speaker>
          <lg n="1">
            <l>aaa bbb</l>
            <l>ccc ddd</l>
          </lg>
        </sp>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "Alice \u2014",
        "    # 1",
        "    aaa bbb",
        "    ccc ddd",
    ]


def test_sp_multi_block_indent(tmp_path):
    """All blocks inside <sp> are indented; speaker only on first block."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <sp n="sp1">
          <speaker>Alice</speaker>
          <p n="p1">hello world</p>
          <lg n="v1">
            <l>aaa</l>
            <l>bbb</l>
          </lg>
        </sp>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "Alice \u2014",
        "    # p1",
        "    hello world",
        "",
        "    # v1",
        "    aaa",
        "    bbb",
    ]


def test_del_elements_excluded(tmp_path):
    """<del> elements should be stripped from plain-text output."""
    xml_path = _write_xml(
        tmp_path,
        '<p n="1">aaa<del>removed</del>bbb</p>',
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# 1",
        "aaabbb",
    ]


def test_stage_directions_indented(tmp_path):
    """Standalone <stage> inside <p> should be indented."""
    xml_path = _write_xml(
        tmp_path,
        textwrap.dedent("""\
        <div n="1">
          <p n="p1"><stage>Enter Alice.</stage></p>
          <lg n="v1">
            <l>aaa</l>
          </lg>
          <p n="p2"><stage>Exit Alice.</stage></p>
        </div>"""),
    )
    out_path = tmp_path / "out.txt"
    create_plain_text(_make_text(), out_path, xml_path)

    assert _content_lines(out_path) == [
        "",
        "# p1",
        "    (Enter Alice.)",
        "",
        "# v1",
        "aaa",
        "",
        "# p2",
        "    (Exit Alice.)",
    ]
