from dataclasses import dataclass
from xml.etree import ElementTree as ET
from typing import Optional

from indic_transliteration import sanscript


@dataclass
class Rule:
    tag: Optional[str]
    attrib: dict[str, str]
    text_before: str
    text_after: str


def text(before="", after=""):
    return Rule(None, None, before, after)


def elem(name, attrs, before="", after=""):
    return Rule(name, attrs, before, after)


transforms = {
    "lg": elem("p", {"class": "x-verse"}),
    "l": elem("span", {"class": "x-pada"}),
    "section": elem("section", {}),
}


def transform(blob: str) -> str:
    root = ET.fromstring(blob)

    for elem in root.iter():
        rule = transforms[elem.tag]
        elem.tag = rule.tag
        elem.attrib = rule.attrib
        elem.text = sanscript.transliterate(
            elem.text, sanscript.HK, sanscript.DEVANAGARI
        )
    return ET.tostring(root, encoding="utf-8").decode("utf-8")
