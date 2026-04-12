from xml.etree import ElementTree as ET

import ambuda.utils.xml as x


def test_delete():
    xml = ET.fromstring('<div><paren class="foo">test</paren>after</div>')
    paren = xml[0]
    x._delete(paren)
    assert paren.tag is None
    assert paren.attrib == {}
    assert paren.text is None
    assert paren.tail is None


def test_text_of():
    xml = ET.fromstring('<div><paren class="foo">test</paren></div>')
    assert x._text_of(xml, "./paren", default="bar") == "test"
    assert x._text_of(xml, "./missing", default="bar") == "bar"


def test_sanskrit_text():
    xml = ET.fromstring("<s><b>a</b>i</s>")
    x.sanskrit_text(xml)
    assert (
        ET.tostring(xml, encoding="utf-8").decode("utf-8")
        == '<span lang="sa"><b>अ</b>इ</span>'
    )


def test_paren_rule__text_only():
    xml = ET.fromstring("<paren>test</paren>")
    x.paren_rule(xml)
    output = ET.tostring(xml).decode("utf-8")
    assert output == '<span class="paren">(test)</span>'


def test_paren_rule__text_and_child():
    xml = ET.fromstring("<paren>test <b>foo</b></paren>")
    x.paren_rule(xml)
    output = ET.tostring(xml).decode("utf-8")
    assert output == '<span class="paren">(test <b>foo</b>)</span>'


def test_transform_text_block():
    blob = '<lg xml:id="Test">verse</lg>'
    block = x.transform_text_block(blob)
    assert block == "<s-lg>verse</s-lg>"


def test_transform_text_block__subst_keeps_add_drops_del():
    blob = '<p xml:id="T">aaa<subst><del>old</del><add>new</add></subst>bbb</p>'
    result = x.transform_text_block(blob)
    assert result == '<s-p xml:id="T">aaanewbbb</s-p>'


def test_transform_text_block__subst_add_before_del():
    blob = '<p xml:id="T">aaa<subst><add>new</add><del>old</del></subst>bbb</p>'
    result = x.transform_text_block(blob)
    assert result == '<s-p xml:id="T">aaanewbbb</s-p>'


def test_transform_text_block__lone_del_removed():
    blob = '<p xml:id="T">aaa<del>removed</del>bbb</p>'
    result = x.transform_text_block(blob)
    assert result == '<s-p xml:id="T">aaabbb</s-p>'


def test_transform_text_block__lone_add_kept():
    blob = '<p xml:id="T">aaa<add>inserted</add>bbb</p>'
    result = x.transform_text_block(blob)
    assert result == '<s-p xml:id="T">aaainsertedbbb</s-p>'


def test_transform():
    blob = "<div>This is a <span>test</span> of our xml code.</div>"
    transforms = {
        "div": x.elem("p"),
        "span": x.elem("strong"),
    }
    xml = ET.fromstring(blob)
    output = x.transform(xml, transforms)
    assert output == "<p>This is a <strong>test</strong> of our xml code.</p>"


def test_parse_tei_header():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title type="main">TITLE</title>
          <title type="sub">A machine-readable edition</title>
          <author>AUTHOR</author>
        </titleStmt>
        <publicationStmt>
          <publisher>Ambuda</publisher>
          <!-- "free" or "restricted" depending on the license-->
          <availability status="AVAILABILITY">
            <license>
              TODO
            </license>
          </availability>
          <date>{current_year}</date>
        </publicationStmt>
        <sourceDesc>
          <bibl>
            <title>BIBL_TITLE</title>
            <author>BIBL_AUTHOR</author>
            <editor>BIBL_EDITOR</editor>
            <publisher>BIBL_PUBLISHER</publisher>
            <pubPlace>BIBL_PUB_PLACE</pubPlace>
            <date>BIBL_PUB_YEAR</date>
          </bibl>
        </sourceDesc>
      </fileDesc>
      <encodingDesc>
        <projectDesc>
          <p>Produced through the distributed proofreading interface on Ambuda.</p>
        </projectDesc>
      </encodingDesc>
      <revisionDesc>
        TODO
      </revisionDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    # Electronic text fields (from titleStmt / publicationStmt)
    assert parsed.tei_title == "TITLE"
    assert parsed.tei_author == "AUTHOR"
    assert parsed.tei_publisher == "Ambuda"
    assert parsed.tei_publication_year == "{current_year}"
    # Source edition fields (from sourceDesc/bibl)
    assert parsed.source_author == "BIBL_AUTHOR"
    assert parsed.source_editor == "BIBL_EDITOR"
    assert parsed.source_publisher == "BIBL_PUBLISHER"
    assert parsed.source_publisher_place == "BIBL_PUB_PLACE"
    assert parsed.source_publication_year == "BIBL_PUB_YEAR"


def test_parse_tei_header__author_fallback_to_titlestmt():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
          <author>TITLESTMT_AUTHOR</author>
        </titleStmt>
        <sourceDesc>
          <bibl>
            <title>Some Title</title>
          </bibl>
        </sourceDesc>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert parsed.tei_author == "TITLESTMT_AUTHOR"


def test_parse_tei_header__source_unstructured_bibl():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
        <sourceDesc>
          <bibl>Smith, J. (1990). A Great Book. Publisher.</bibl>
        </sourceDesc>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert parsed.source_citation == "Smith, J. (1990). A Great Book. Publisher."


def test_parse_tei_header__credits():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
          <respStmt>
            <resp>Data entry</resp>
            <name>Alice</name>
            <name>Bob</name>
          </respStmt>
          <respStmt>
            <resp>Proofreading</resp>
            <name>Charlie</name>
          </respStmt>
        </titleStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert parsed.credits == [
        ("Data entry", ["Alice", "Bob"]),
        ("Proofreading", ["Charlie"]),
    ]


def test_parse_tei_header__credits_persname():
    header = """
    <teiHeader>
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
          <respStmt>
            <persName>Alice</persName>
            <resp>Creation of machine-readable version.</resp>
          </respStmt>
          <respStmt>
            <name>Bob</name>
            <resp>Proofreading</resp>
          </respStmt>
        </titleStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert parsed.credits == [
        ("Creation of machine-readable version.", ["Alice"]),
        ("Proofreading", ["Bob"]),
    ]


def test_parse_tei_header__notes():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
        <notesStmt>
          <note type="legacyheader">legacy stuff</note>
          <note>This text was sourced from GRETIL.</note>
        </notesStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert "This text was sourced from GRETIL." in parsed.notes


def test_parse_tei_header__notes_with_ref():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
        <notesStmt>
          <note>See <ref target="http://example.com">this page</ref> for details.</note>
        </notesStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert '<a href="http://example.com">this page</a>' in parsed.notes
    assert "See" in parsed.notes
    assert "for details." in parsed.notes


def test_parse_tei_header__notes_with_lb():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
        <notesStmt>
          <note>Line one<lb />Line two</note>
        </notesStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert "<br" in parsed.notes
    assert "Line one" in parsed.notes
    assert "Line two" in parsed.notes


def test_parse_tei_header__revision_desc():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
      </fileDesc>
      <revisionDesc>
        <change when="2020-01-01">Initial encoding</change>
        <change when="2021-06-15">Added metadata</change>
      </revisionDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert len(parsed.revision_desc) == 2
    assert parsed.revision_desc[0] == {
        "date": "2020-01-01",
        "who": "",
        "description": "Initial encoding",
    }
    assert parsed.revision_desc[1] == {
        "date": "2021-06-15",
        "who": "",
        "description": "Added metadata",
    }


def test_parse_tei_header__publication_year_separation():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
          <title>TITLE</title>
        </titleStmt>
        <publicationStmt>
          <date when-iso="2020">2020</date>
        </publicationStmt>
        <sourceDesc>
          <bibl>
            <title>Some Title</title>
          </bibl>
        </sourceDesc>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    # publicationStmt date goes to tei_publication_year, not publication_year
    assert parsed.tei_publication_year == "2020"
    assert parsed.source_publication_year == ""


def test_parse_tei_header__elements_missing():
    header = """
    <teiHeader xml:lang="en">
      <fileDesc>
        <titleStmt>
        </titleStmt>
      </fileDesc>
    </teiHeader>
    """
    parsed = x.parse_tei_header(header)
    assert parsed.tei_title == "Unknown"
    assert parsed.tei_author == "Unknown"
    assert parsed.source_author == ""
    assert parsed.source_editor == ""
    assert parsed.source_publisher == ""
    assert parsed.source_publication_year == ""
    assert parsed.source_citation == ""
    assert parsed.tei_publisher == ""
    assert parsed.tei_publication_year == ""
    assert parsed.tei_availability == ""
    assert parsed.credits is None
    assert parsed.notes == ""
    assert parsed.revision_desc is None


def test_parse_tei_header__undefined():
    assert x.parse_tei_header(None) == {}
