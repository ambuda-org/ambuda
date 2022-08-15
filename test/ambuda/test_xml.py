from xml.etree import ElementTree as ET

import ambuda.xml as x


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
    assert block.id == "Test"
    assert block.html == "<s-lg>verse</s-lg>"


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
    assert parsed["title"] == "TITLE"
    assert parsed["author"] == "AUTHOR"
    assert parsed["publisher"] == "Ambuda"


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
    assert parsed["title"] == "Unknown"
    assert parsed["author"] == "Unknown"
    assert parsed["publisher"] == "Unknown"


def test_parse_tei_header__undefined():
    assert x.parse_tei_header(None) == {}
