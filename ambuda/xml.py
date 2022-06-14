from dataclasses import dataclass
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript


@dataclass
class Rule:

    """Describes how to modify an XML element."""

    tag: str
    attrib: dict
    text_before: str
    text_after: str

    def __call__(self, el):
        el.tag = self.tag
        el.attrib = self.attrib
        if self.text_before:
            el.text = self.text_before + (el.text or "")
        if self.text_after:
            el.tail = self.text_after + (el.tail or "")


def elem(tag, attrib=None, text_before="", text_after=""):
    """Helper to rename an element and change its attributes."""
    return Rule(tag, attrib or {}, text_before, text_after)


def text(before="", after=""):
    """Replace an element with plain text."""
    return Rule(None, {}, before, after)


def sanskrit_text(xml):
    """Transliterate inline elements."""
    t = sanscript.transliterate
    xml.tag = "span"
    xml.attrib = {"lang": "sa"}
    for el in xml.iter("*"):
        if el.text:
            el.text = t(el.text, sanscript.SLP1, sanscript.DEVANAGARI)
        # Ignore xml.tail
        if el.tail and el is not xml:
            el.tail = t(el.tail, sanscript.SLP1, sanscript.DEVANAGARI)


#: Wrap in parentheses.
paren_rule = Rule("span", {"class": "paren"}, "(", ")")
#: Wrap in brackets.
bracket_rule = Rule("span", {"class": "paren"}, "[", "]")


# Tag meanings are documented here:
# https://www.sanskrit-lexicon.uni-koeln.de/talkMay2008/mwtags.html
mw_xml = {
    # Root elements
    "H1": None,
    "H1A": None,
    "H1B": None,
    "H1E": None,
    "H2": None,
    "H2A": None,
    "H2B": None,
    "H3": None,
    "H3A": None,
    "H3B": None,
    "H4": None,
    "H4A": None,
    "H4B": None,
    # Record structure
    "h": None,
    "body": elem("li", {"class": "dict-entry mw-entry"}),
    "tail": None,
    # Head information -- hide all of it.
    "hc1": None,
    "hc3": None,
    "key1": None,
    "key2": None,
    # Body -- special characters
    "b": bracket_rule,
    "b1": bracket_rule,
    "p": paren_rule,
    "p1": paren_rule,
    "quote": elem("q"),
    "sr": text("\u00b0"),
    "sr1": text("\u00b0"),
    "abE": None,
    "srs": text(""),
    "srs1": text(""),
    "shc": None,
    "shortlong": None,
    "auml": text("ä"),
    "euml": text("ë"),
    "ouml": text("ö"),
    "uuml": text("ü"),
    "etc": text("&c"),
    "etc1": text("&c"),
    "etcetc": text("&c"),
    "amp": text("&"),
    "eq": elem("abbr", None, text_before="="),
    "fs": text("/"),
    "msc": text(";"),
    "ccom": None,
    "ab": elem("abbr"),
    "etym": elem("i"),
    "s": sanskrit_text,
    "ns": elem("span"),
    "s1": elem("span"),
    "bio": elem("b"),
    "bot": elem("b"),
    "root": text("\u221a"),
    "ls": elem("cite"),
    "lex": elem("span", {"class": "lex"}),
    "vlex": elem("span", {"class": "lex"}),
    "hom": None,
    "info": None,
    "lang": elem("span"),
    # Also distinct tail pc, should be treated differently
    "pc": None,
    "pcol": elem("span"),
    "cf": elem("abbr", text_before="cf."),
    "qv": elem("abbr", text_before="q.v."),
    "see": text(" see "),
    # Tail elements
    "L": None,
    "MW": None,
    "mul": None,
    "mat": None,
    "mscverb": None,
    # Other
    "pb": None,
}
apte_xml = {
    "ab": elem("abbr"),
    "b": elem("b"),
    "br": elem("br"),
    "i": elem("i"),
    "body": elem("li", {"class": "dict-entry mw-entry"}),
    "lb": elem("div", {"class": "h-2"}, " "),
    "lbinfo": None,
    "ls": elem("cite"),
    "s": sanskrit_text,
    # TODO: keep attrs
    "span": elem("span"),
}
vacaspatyam_xml = {
    "body": elem("li", {"class": "dict-entry"}),
    "s": sanskrit_text,
    "lb": elem("div", {"class": "h-2"}, " "),
    "b": elem("b"),
}


def to_verse(el):
    xml_id = "{http://www.w3.org/XML/1998/namespace}id"
    el.tag = "s-lg"
    el.attrib = {"id": el.attrib.get(xml_id, "")}
    print(list(el.attrib.keys()))


# Defined against the TEI spec
tei_xml = {
    "div": elem("section"),
    "seg": elem("span"),
    "hi": text(),
    "note": None,
    "orig": elem("span"),
    "lg": to_verse,
    "l": elem("s-l"),
    "section": elem("section"),
}

# Tag meanings are documented here:
# https://www.sanskrit-lexicon.uni-koeln.de/talkMay2008/mwtags.html
apte_transforms = {
    "ab": elem("abbr"),
    "b": elem("b"),
    "br": elem("br"),
    "i": elem("i"),
    "body": elem("li", {"class": "mw-entry"}),
    "lb": elem("div", {"class": "h-2"}, " "),
    "lbinfo": None,
    "ls": elem("cite"),
    "s": elem("span", {"lang": "sa"}, "##", "##"),
    # TODO: keep attrs
    "span": elem("span"),
}


def transform(blob, transforms):
    xml = ET.fromstring(blob)
    for el in xml.iter("*"):
        if el.tag in transforms:
            fn = transforms[el.tag]
            if fn is None:
                # Don't delete the tail, as that would delete meaningful text.
                el.tag = el.text = None
            else:
                fn(el)
    return ET.tostring(xml, encoding="utf-8").decode("utf-8")


def transform_mw(blob):
    return transform(blob, mw_xml)


def transform_apte(blob):
    return transform(blob, apte_xml)


def transform_vacaspatyam(blob):
    return transform(blob, vacaspatyam_xml)


def transform_tei(blob):
    xml = ET.fromstring(blob)
    for el in xml.iter("*"):
        if el.tag in tei_xml:
            fn = tei_xml[el.tag]
            if fn is None:
                # Don't delete the tail, as that would delete meaningful text.
                el.tag = el.text = None
            else:
                fn(el)

    t = sanscript.transliterate
    xml.attrib["lang"] = "sa"
    for el in xml.iter("*"):
        if el.text:
            el.text = t(el.text, sanscript.HK, sanscript.DEVANAGARI)
        # Ignore xml.tail
        if el.tail and el is not xml:
            el.tail = t(el.tail, sanscript.HK, sanscript.DEVANAGARI)

    return ET.tostring(xml, encoding="utf-8").decode("utf-8")
