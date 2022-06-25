"""Functions for transforming XML into HTML.


Method
------
We store most of our content in the database at XML. At request time, we fetch
these XML strings and convert them into HTML.

We use this transformation approach (as opposed to storing HTML directly in the
database) so that we can easily make changes to the underlying HTML. If we add
a new class to an HTML element, for example, that change can go into effect
immediately. If we stored raw HTML instead, we would have to rebuild most of
the database each time we change this content's presentation.

We use different source documents for each XML "source." For example, the
Monier-Williams dictionary uses different XML conventions from a TEI document,
so we handle them with different functions.


Performance
-----------
In Python 3, `ElementTree` uses the C implementation by default, so the
performance penalty for this work is minimal. In the future, we can also cache
or pre-build common requests.
"""

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript


@dataclass
class Rule:

    """Describes how to modify an XML element."""

    #: The tag to apply to this element.
    tag: str
    #: Attributes to apply to this element.
    attrib: dict
    #: Text to insert before this element's `text` field.
    text_before: str
    #: Text to insert after this element's `tail` field.
    text_after: str

    def __call__(self, el: ET.Element):
        el.tag = self.tag
        el.attrib = self.attrib
        if self.text_before:
            el.text = self.text_before + (el.text or "")
        if self.text_after:
            el.tail = self.text_after + (el.tail or "")


def elem(tag, attrib=None, text_before="", text_after="") -> Rule:
    """Helper to rename an element and change its attributes."""
    return Rule(tag, attrib or {}, text_before, text_after)


def text(before="", after="") -> Rule:
    """Replace an element with plain text."""
    return Rule(None, {}, before, after)


def sanskrit_text(xml: ET.Element):
    """Transliterate inline elements in-place."""
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


def to_verse(el: ET.Element):
    # "xml:id" can't be specified directly due to how ElementTree treats
    # namespaces. So, hard-code it like this:
    xml_id = "{http://www.w3.org/XML/1998/namespace}id"
    # "-" is the HTML syntax for custom elements.
    el.tag = "s-lg"
    el.attrib = {"id": el.attrib.get(xml_id, "")}


# Defined against the TEI spec
tei_xml = {
    "head": elem("h1"),
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


def transform(xml: ET.Element, transforms: dict[str, Rule]):
    for el in xml.iter("*"):
        if el.tag in transforms:
            fn = transforms[el.tag]
            if fn is None:
                # Don't delete the tail, as that would delete meaningful text.
                el.tag = el.text = None
            else:
                fn(el)
    return ET.tostring(xml, encoding="utf-8").decode("utf-8")


def transform_mw(blob) -> str:
    """Transform XML for the Monier-Williams dictionary."""
    xml = ET.fromstring(blob)
    return transform(xml, mw_xml)


def transform_apte(blob) -> str:
    """Transform XML for the Apte dictionary."""
    xml = ET.fromstring(blob)
    return transform(xml, apte_xml)


def transform_vacaspatyam(blob) -> str:
    """Transform XML for the Vacaspatyam."""
    xml = ET.fromstring(blob)
    return transform(xml, vacaspatyam_xml)


def transform_tei(blob) -> str:
    """Transform XML for a TEI document."""
    xml = ET.fromstring(blob)
    return transform(xml, tei_xml)


def transform_sak(blob) -> str:
    """Transform XML for the Shabdarthakaustubha."""
    xml = ET.fromstring(blob)
    # Reuse the Vacaspatyam xml config, since it's close enough.
    return transform(xml, vacaspatyam_xml)
