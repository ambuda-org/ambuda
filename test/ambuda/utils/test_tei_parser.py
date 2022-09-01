import xml.etree.ElementTree as ET

import ambuda.utils.tei_parser as tei


def test_delete_unused_elements():
    blob = "".join(
        [
            "<lg>"
            "<l><seg>segment</seg> <hi>hi</hi></l>"
            "<l>text<note>note</note></l>"
            "</lg>"
        ]
    )
    xml = ET.fromstring(blob)
    tei._delete_unused_elements(xml)

    actual = ET.tostring(xml, encoding="utf-8").decode("utf-8")
    assert actual == "<lg><l>segment hi</l><l>text</l></lg>"


def test_to_devanagari():
    xml = ET.fromstring("<div><span>a</span>ka</div>")
    tei._to_devanagari(xml)

    actual = ET.tostring(xml, encoding="utf-8").decode("utf-8")
    assert actual == "<div><span>अ</span>क</div>"


def test_create_section():
    blob = "".join(
        [
            "<div>",
            "<lg xml:id='Test.1'>a</lg>",
            "<lg xml:id='Test.2'>b</lg>",
            "<lg xml:id='Test.3'>c</lg>",
            "</div>",
        ]
    )
    xml = ET.fromstring(blob)
    tei._remove_namespace(xml, "{" + tei.NS["tei"] + "}")
    section = tei._create_section(xml, "s1")

    assert section.slug == "s1"
    assert len(section.blocks) == 3
    assert [x.slug for x in section.blocks] == ["s1.1", "s1.2", "s1.3"]
    assert [x.blob for x in section.blocks] == [
        '<lg xml:id="Test.1">a</lg>',
        '<lg xml:id="Test.2">b</lg>',
        '<lg xml:id="Test.3">c</lg>',
    ]
