from xml.etree import ElementTree as ET

from ambuda.xml import elem, transform, paren_rule


def test_paren__text_only():
    xml = ET.fromstring("<paren>test</paren>")
    paren_rule(xml)
    output = ET.tostring(xml).decode("utf-8")
    assert output == '<span class="paren">(test)</span>'


def test_paren__text_and_child():
    xml = ET.fromstring("<paren>test <b>foo</b></paren>")
    paren_rule(xml)
    output = ET.tostring(xml).decode("utf-8")
    assert output == '<span class="paren">(test <b>foo</b>)</span>'


def test_transform():
    blob = "<div>This is a <span>test</span> of our xml code.</div>"
    transforms = {
        "div": elem("p"),
        "span": elem("strong"),
    }
    xml = ET.fromstring(blob)
    output = transform(xml, transforms)
    assert output == "<p>This is a <strong>test</strong> of our xml code.</p>"
