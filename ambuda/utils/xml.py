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

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NewType
from xml.etree import ElementTree as ET

from lxml import etree
from lxml.html import fragment_fromstring, tostring as html_tostring

import defusedxml.ElementTree as DET
from ambuda.utils.vidyut_shim import transliterate, Scheme

Attributes = NewType("Attributes", dict[str, str])


def indent_xml_file_in_place(path: Path) -> None:
    """Re-parse an XML file, indent it, and write it back."""
    tree = etree.parse(str(path))
    etree.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


@dataclass
class ParsedTEIHeader:
    # Electronic text (from titleStmt / publicationStmt)
    tei_title: str = "Unknown"
    tei_author: str = "Unknown"
    tei_publisher: str = ""
    tei_publication_year: str = ""
    tei_availability: str = ""
    credits: list[tuple[str, list[str]]] | None = None
    notes: str = ""
    revision_desc: list[dict] | None = None
    # Source edition (from sourceDesc/bibl)
    source_author: str = ""
    source_editor: str = ""
    source_publisher: str = ""
    source_publisher_place: str = ""
    source_publication_year: str = ""
    source_citation: str = ""

    @property
    def has_source_info(self) -> bool:
        return bool(
            self.source_author
            or self.source_editor
            or self.source_publisher
            or self.source_publisher_place
            or self.source_publication_year
            or self.source_citation
        )


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
            if len(el):
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


def _delete(xml: ET.Element):
    xml.clear()
    xml.tag = None


def _strip(xml: ET.Element):
    """Remove the element and its contents, but keep its tail text."""
    tail = xml.tail
    xml.clear()
    xml.tail = tail
    xml.tag = None


def elem(tag, attrib=None, text_before="", text_after="") -> Rule:
    """Helper to rename an element and change its attributes."""
    return Rule(tag, _overwrite(attrib or {}), text_before, text_after)


def text(before="", after="") -> Rule:
    """Replace an element with plain text."""
    return Rule(None, _overwrite({}), before, after)


def sanskrit_text(xml: ET.Element):
    """Transliterate inline elements in-place."""
    xml.tag = "span"
    xml.attrib = {"lang": "sa"}
    for el in xml.iter("*"):
        if el.text:
            el.text = transliterate(el.text, Scheme.Slp1, Scheme.Devanagari)
        # Ignore xml.tail
        if el.tail and el is not xml:
            el.tail = transliterate(el.tail, Scheme.Slp1, Scheme.Devanagari)


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

amarakosha_xml = {
    "body": elem("li", {"class": "dict-entry"}),
    "lex": elem("span", {"class": "lex"}),
    "s": sanskrit_text,
    "lb": elem("div", {"class": "h-2"}, " "),
    "quote": elem("blockquote", {"class": "ml-4"}),
    "lg": elem("p"),
    "l": elem("span", {"class": "block"}),
}


#: Transforms for Apte's Sanskrit-Hindi dictionary from the University of
#: Hyderabad.
apte_uoh_xml = {
    # TODO:
    # Entry
    "lexhead": elem("li", {"class": "dict-entry mw-entry"}),
    "segmenthd": elem("li", {"class": "dict-entry mw-entry"}),
    # Key
    "dentry": sanskrit_text,
    # Bare stem (redundant given `dentry')
    "prAwipaxikam": None,
    # Part of speech and derivation
    "grammar": elem("span", {"class": "lex"}),
    "etymology": elem("span", {"class": "lex"}),
    # Definitions
    "sense": elem("div", {"class": "m-2"}, " "),
    # Citation
    # FIXME: <citation> has no space before it. `text_before` inserts text
    # after opening tag, but here we want text *before* the opening tag.
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
    "lb": elem("br"),
    "change": elem("p"),
}


def _handle_tei_p(el: ET.Element):
    if el.tag == "p":
        el.tag = "s-p"

    # If <p> contains only a <stage>, center the stage.
    if not el.text and len(el) == 1 and el[0].tag == "stage" and not el[0].tail:
        el.attrib["class"] = "text-center"


def _handle_tei_choice(el: ET.Element):
    # choice between sic and corr -- always keep corr, toss sic.

    # chaya
    attr_lang = "{http://www.w3.org/XML/1998/namespace}lang"
    if el.attrib.get("type") == "chaya":
        for seg in el:
            if seg.attrib.get(attr_lang) == "sa":
                seg.attrib["class"] = "s-chaya"
    else:
        # sic / corr -- taken care of, as <sic> is just deleted.
        pass


def _handle_tei_stage(el: ET.Element):
    el.tag = "s-stage"
    el.text = f"( {el.text or ''} )"


def _handle_tei_seg(el: ET.Element):
    el.tag = "span"


# Defined against the TEI spec
# TODO: footnote-ref, footnote, chaya
tei_xml = {
    # Headers and trailers
    "title": None,
    "subtitle": None,
    "head": elem("h1"),
    "trailer": elem("s-trailer"),
    # Section
    "div": elem("section"),
    "section": elem("section"),
    # Standard block elements
    "lg": elem("s-lg", {}),
    "l": elem("s-l"),
    "p": _handle_tei_p,
    # Stages and speakers
    "sp": elem("s-sp", {}),
    "speaker": elem("s-speaker", {}, text_after=" —"),
    "stage": _handle_tei_stage,
    "lb": elem("br"),
    # Inline elements
    "choice": _handle_tei_choice,
    "sic": None,
    # For <subst>, unwrap the element: its <del> children are stripped and
    # its <add> children are unwrapped, leaving only the inserted text.
    "subst": text(),
    "add": text(),
    "del": _strip,
    # A segment of text (e.g. a pāda).
    "seg": _handle_tei_seg,
    "hi": text(),
    "orig": elem("span"),
    # Footnotes (currently not supported.)
    "note": None,
    "ref": None,
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
    xml = DET.fromstring(blob)
    return transform(xml, mw_xml)


def transform_apte_sanskrit_english(blob: str) -> str:
    """Transform XML for the Apte Sanskrit-English dictionary."""
    xml = DET.fromstring(blob)
    return transform(xml, apte_cologne_xml)


def transform_apte_sanskrit_hindi(blob: str) -> str:
    """Transform XML for the Apte Sanskrit-Hindi dictionary."""
    xml = DET.fromstring(blob)
    return transform(xml, apte_uoh_xml)


def transform_vacaspatyam(blob: str) -> str:
    """Transform XML for the Vacaspatyam."""
    xml = DET.fromstring(blob)
    return transform(xml, vacaspatyam_xml)


def transform_amarakosha(blob: str) -> str:
    """Transform XML for the Amarakosha."""
    xml = DET.fromstring(blob)
    return transform(xml, amarakosha_xml)


def _text_of(xml: ET.Element, path: str, default: str) -> str:
    """Get the text of the given XML element."""
    try:
        return xml.find(path).text
    except AttributeError:
        return default


def parse_tei_header(blob: str | None) -> ParsedTEIHeader:
    """Transform a TEI `teiHeader` element to HTML."""
    if not blob:
        return {}

    xml = DET.fromstring(blob)

    file_desc = xml.find("./fileDesc")

    # publicationStmt
    tei_publisher = _text_of(file_desc, "./publicationStmt/publisher", "")
    tei_availability = ""
    availability_xml = file_desc.find("./publicationStmt/availability")
    if availability_xml is not None:
        tei_availability = transform(availability_xml, tei_header_xml)
    tei_publication_year = ""
    pub_date_el = file_desc.find("./publicationStmt/date")
    if pub_date_el is not None:
        tei_publication_year = (
            pub_date_el.get("when-iso", "")
            or pub_date_el.get("when", "")
            or pub_date_el.text
            or ""
        )

    # titleStmt
    author = _text_of(file_desc, "./titleStmt/author", "Unknown")

    # sourceDesc
    source_author = _text_of(file_desc, "./sourceDesc/bibl/author", "")
    source_editor = _text_of(file_desc, "./sourceDesc/bibl/editor", "")
    source_publication_year = _text_of(file_desc, "./sourceDesc/bibl/date", "")
    source_citation = ""
    bibl_el = file_desc.find("./sourceDesc/bibl")
    if bibl_el is not None and len(bibl_el) == 0:
        source_citation = (bibl_el.text or "").strip()

    credits = []
    for resp_stmt in file_desc.findall("./titleStmt/respStmt"):
        resp_el = resp_stmt.find("resp")
        resp_text = (resp_el.text or "").strip() if resp_el is not None else ""
        names = [
            n.text.strip()
            for tag in ("name", "persName")
            for n in resp_stmt.findall(tag)
            if n.text and n.text.strip()
        ]
        if resp_text or names:
            credits.append((resp_text, names))

    # notesStmt
    notes = ""
    notes_stmt = file_desc.find("./notesStmt")
    if notes_stmt is not None:
        for note_el in notes_stmt.findall("note"):
            if note_el.get("type") == "legacyheader":
                continue
            note_el.tag = "span"
            notes = transform(note_el, tei_header_xml).strip()
            if notes:
                break

    # revisionDesc
    revision_entries = []
    rev_desc_el = xml.find("./revisionDesc")
    if rev_desc_el is not None:
        for change_el in rev_desc_el.findall(".//change"):
            date = change_el.get("when") or change_el.get("when-iso") or ""
            who = change_el.get("who", "")
            # Strip leading # from @who (TEI convention for internal references)
            if who.startswith("#"):
                who = who[1:]
            description = "".join(change_el.itertext()).strip()
            if description or date:
                revision_entries.append(
                    {"date": date, "who": who, "description": description}
                )

    return ParsedTEIHeader(
        tei_title=_text_of(file_desc, "./titleStmt/title", "Unknown"),
        tei_author=author,
        tei_publisher=tei_publisher,
        tei_publication_year=tei_publication_year,
        tei_availability=tei_availability,
        credits=credits or None,
        notes=notes,
        revision_desc=revision_entries or None,
        source_author=source_author,
        source_editor=source_editor,
        source_publisher=_text_of(file_desc, "./sourceDesc/bibl/publisher", ""),
        source_publisher_place=_text_of(file_desc, "./sourceDesc/bibl/pubPlace", ""),
        source_publication_year=source_publication_year,
        source_citation=source_citation,
    )


def transform_sak(blob: str) -> str:
    """Transform XML for the Shabdarthakaustubha."""
    xml = DET.fromstring(blob)
    # Reuse the Vacaspatyam xml config, since it's close enough.
    return transform(xml, vacaspatyam_xml)


def transform_text_block(block_blob: str) -> str:
    """Transform XML for a TEI document.

    :param block_blob: the original XML blob for this block.
    :return: the HTML transform of that XML blob
    """
    # FIXME: leaky abstraction. We should return just a string blob here and
    # get the XML ID from `database.Block` instead.
    xml = DET.fromstring(block_blob)
    return transform(xml, transforms=tei_xml)


def transliterate_html(html: str, source: Scheme, dest: Scheme) -> str:
    has_text_work = source != dest
    has_lemma_work = dest != Scheme.Slp1
    if not has_text_work and not has_lemma_work:
        return html

    root = fragment_fromstring(html, create_parent="div")
    for el in root.iter():
        if el.attrib.get("lang") == "en":
            continue

        if has_text_work:
            if el.text:
                el.text = transliterate(el.text, source, dest)
            if el.tail and el is not root:
                el.tail = transliterate(el.tail, source, dest)

        if has_lemma_work and el.tag == "s-w" and "lemma" in el.attrib:
            el.attrib["lemma"] = transliterate(el.attrib["lemma"], Scheme.Slp1, dest)

    parts = []
    if root.text:
        parts.append(root.text)
    for child in root:
        parts.append(html_tostring(child, encoding="unicode"))
    return "".join(parts)
