from xml.etree import ElementTree as ET

from ambuda.xml import elem, transform


def test_transform():
    blob = "<div>This is a <span>test</span> of our xml code.</div>"
    transforms = {
        "div": elem("p"),
        "span": elem("strong"),
    }
    xml = ET.fromstring(blob)
    output = transform(xml, transforms)
    assert output == "<p>This is a <strong>test</strong> of our xml code.</p>"
