"""Functions for transforming XML into HTML.


Approach
--------
We store most of our content in the database at XML. At request time, we fetch
these XML strings and convert them into HTML.

We use this transformation approach (as opposed to storing HTML directly in the
database) so that we can easily make changes to the underlying HTML. If we add
a new class to an HTML element, for example, that change can go into effect
immediately. If we stored raw HTML instead, we would have to rebuild most of
the database each time we change this content's presentation.

We use different transformation functions for each XML "source." For example,
the Monier-Williams dictionary uses different XML conventions from a TEI
document, so we handle them with different functions.


Performance
-----------
In Python 3, `ElementTree` uses the C implementation by default, so the
performance penalty for this work is minimal. In the future, we can also cache
or pre-build common requests.
"""

from dataclasses import dataclass
from typing import Callable, NewType, Optional
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript

Attributes = NewType("Attributes", dict[str, str])


@dataclass
class Rule:

    """Describes how to modify an XML element."""

    #: The tag to apply to this element.
    tag: str
    #: Function that transforms the element's existing attributes into our
    #: desired format.
    attrib_fn: Callable
    #: Text to insert before this element's `text` field.
    text_before: str = ""
    #: Text to insert after this element's `tail` field.
    text_after: str = ""

    def __call__(self, el: ET.Element):
        el.tag = self.tag
        el.attrib = self.attrib_fn(el.attrib)
        if self.text_before:
            el.text = self.text_before + (el.text or "")
        if self.text_after:
            if el:
                el[-1].tail = (el.tail or "") + self.text_after
            else:
                el.text = (el.text or "") + self.text_after


def _overwrite(new_attrib: Attributes) -> Callable:
    """Remove the element's existing attributes and use `new_attrib` instead."""

    def inner(_: Attributes) -> Attributes:
        return new_attrib

    return inner


def _rename(mapping: dict[str, str]) -> Callable:
    """Rename the element's existing attributes.

    Attributes not defined in the mapping are removed from the output.
    """

    def inner(old_attrib: Attributes) -> Attributes:
        new_attrib = {}
        for k, v in mapping.items():
            if k in old_attrib:
                new_attrib[v] = old_attrib[k]
        return new_attrib

    return inner


@dataclass
class Block:
    #: The block's HTML id.
    id: str
    #: HTML content for the given block.
    html: str


def _delete(xml: ET.Element):
    xml.clear()
    xml.tag = None


def elem(tag, attrib=None, text_before="", text_after="") -> Rule:
    """Helper to rename an element and change its attributes."""
    return Rule(tag, _overwrite(attrib or {}), text_before, text_after)


def text(before="", after="") -> Rule:
    """Replace an element with plain text."""
    return Rule(None, _overwrite({}), before, after)


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
paren_rule = elem("span", {"class": "paren"}, "(", ")")
#: Wrap in brackets.
bracket_rule = elem("span", {"class": "paren"}, "[", "]")


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

# Tag meanings are documented here:
# https://www.sanskrit-lexicon.uni-koeln.de/talkMay2008/mwtags.html
apte_cologne_xml = {
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
#: Transforms for Apte's Sanskrit-Hindi dictionary from the University of
#: Hyderabad.
apte_uoh_xml = {
    # TODO:
    # Entry
    "lexhead": elem("li", {"class": "dict-entry mw-entry"}),
    # Lookup key
    "dentry": sanskrit_text,
    # Bare stem (redundant given `dentry')
    "prAwipaxikam": None,
    "grammar": elem("span", {"class": "lex"}),
    "etymology": elem("span", {"class": "lex"}),
    "sense": elem("div", {"class": "m-2"}, " "),
    # Citation
    # FIXME: text_before inserts text after opening tag. But here, we want
    # text *before* the opening tag.
    "citation": elem("cite", text_before=" ", text_after=" "),
}

# Defined against the TEI spec
tei_header_xml = {
    "teiHeader": elem("section"),
    "revisionDesc": _delete,
    "profileDesc": _delete,
    "encodingDesc": _delete,
    "notesStmt": _delete,
    "email": elem("kbd"),
    "date": _delete,
    "sourceDesc": None,
    "publisher": None,
    "bibl": elem("p"),
    "licence": elem("p"),
    "ref": Rule("a", _rename({"target": "href"})),
}


# Defined against the TEI spec
tei_xml = {
    # Header information
    "head": elem("h1"),
    # A text section
    "div": elem("section"),
    # A segment of text (e.g. a pāda).
    "seg": elem("span"),
    "hi": text(),
    "note": None,
    "orig": elem("span"),
    # A verse (line group)
    "lg": elem("s-lg", {}),
    # A line break
    "lb": elem("br"),
    # A line
    "l": elem("s-l"),
    "section": elem("section"),
}


def transform(xml: ET.Element, transforms: dict[str, Rule]) -> str:
    for el in xml.iter("*"):
        if el.tag in transforms:
            fn = transforms[el.tag]
            if fn is None:
                # Don't delete the tail, as that would delete meaningful text.
                el.tag = el.text = None
            else:
                fn(el)
    return ET.tostring(xml, encoding="utf-8").decode("utf-8")


def transform_mw(blob: str) -> str:
    """Transform XML for the Monier-Williams dictionary."""
    xml = ET.fromstring(blob)
    return transform(xml, mw_xml)


def transform_apte_sanskrit_english(blob: str) -> str:
    """Transform XML for the Apte Sanskrit-English dictionary."""
    xml = ET.fromstring(blob)
    return transform(xml, apte_cologne_xml)


def transform_apte_sanskrit_hindi(blob: str) -> str:
    """Transform XML for the Apte Sanskrit-Hindi dictionary."""
    xml = ET.fromstring(blob)
    return transform(xml, apte_uoh_xml)


def transform_vacaspatyam(blob: str) -> str:
    """Transform XML for the Vacaspatyam."""
    xml = ET.fromstring(blob)
    return transform(xml, vacaspatyam_xml)


def _text_of(xml: ET.Element, path: str, default: str) -> str:
    """Get the text of the given XML element."""
    try:
        return xml.find(path).text
    except AttributeError:
        return default


def parse_tei_header(blob: Optional[str]) -> dict[str, str]:
    """Transform a TEI `teiHeader` element to HTML."""
    if not blob:
        return {}

    xml = ET.fromstring(blob)

    file_desc = xml.find("./fileDesc")
    availability_xml = file_desc.find("./publicationStmt/availability")
    if availability_xml is not None:
        availability = transform(availability_xml, tei_header_xml)
    else:
        availability = ""

    return {
        "title": _text_of(file_desc, "./titleStmt/title", "Unknown"),
        "author": _text_of(file_desc, "./titleStmt/author", "Unknown"),
        "publisher": _text_of(file_desc, "./publicationStmt/publisher", "Unknown"),
        "availability": availability,
    }


def transform_sak(blob: str) -> str:
    """Transform XML for the Shabdarthakaustubha."""
    xml = ET.fromstring(blob)
    # Reuse the Vacaspatyam xml config, since it's close enough.
    return transform(xml, vacaspatyam_xml)


def transform_text_block(block_blob: str) -> Block:
    """Transform XML for a TEI document."""
    # FIXME: leaky abstraction. We should return just a string blob here and
    # get the XML ID from `database.Block` instead.
    xml = ET.fromstring(block_blob)

    # "xml:id" can't be specified directly due to how ElementTree treats
    # namespaces. So, hard-code it like this:
    id = xml.attrib.get("{http://www.w3.org/XML/1998/namespace}id", "")
    html = transform(xml, transforms=tei_xml)
    return Block(id=id, html=html)
