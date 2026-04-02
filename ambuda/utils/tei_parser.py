"""Utilities for parsing a TEI document.

TEI XML is a rich format for encoding document structure and lineage. We use
the utilities in this module to convert an XML file into a structured
representation that we can more easily load into a database.

For a basic introduction to TEI XML, see:

https://ambuda.readthedocs.io/en/latest/tei-xml.html

NOTE: we assume that all documents are in Sanskrit and run transliteration over
each document with `_to_devanagari`. Once we start supporting translations, we
should change this logic.
"""

from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from ambuda.utils.vidyut_shim import transliterate, Scheme

#: Most texts have multiple sections and use section slugs like "1", "2", etc.
#: If a text has just one section, we create a single "default" section with
#: the slug "all".
SINGLE_SECTION_SLUG = "all"
#: Tags that we support on our display. If a section contains a tag that's not
#: in this list, the code below will raise an error.
SUPPORTED_TAGS = {"lg", "head", "p", "sp", "title", "trailer", "milestone", "pb"}
#: TEI namespace URI.
TEI_NS = "http://www.tei-c.org/ns/1.0"
#: Safe parser: no entity resolution (prevents XXE), tolerant of minor errors.
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, recover=True)


def _tostring(el: etree._Element) -> str:
    """Serialize an element to a unicode string."""
    return etree.tostring(el, encoding="unicode")


@dataclass
class Block:
    """A block of content.

    This usually represents an `<lg>` or `<p>` element.
    """

    #: The URL slug of this block, which we will display in the text URL.
    slug: str
    #: XML blob.
    blob: str


@dataclass
class Section:
    """A group of blocks.

    This represents a `<div>` element.
    """

    #: The URL slug of this section, which we will display in the text URL.
    slug: str
    #: All blocks that belong to this section, including <head> and <trailer>
    #: elements.
    blocks: list[Block]


@dataclass
class Document:
    """A parsed TEI document.

    This represents a `<TEI>` element with all of its relevant content.
    """

    #: <teiHeader> XML blob. We use this to display lineage and sourcing
    #: information on a text's *About* page.
    header: str
    #: All sections that belong to this document.
    sections: list[Section]


_TEI_XMLNS_DECL = b' xmlns="' + TEI_NS.encode() + b'"'


def _strip_namespace_bytes(raw: bytes) -> bytes:
    """Strip the TEI namespace declaration from raw XML bytes before parsing.

    This is much faster than iterating every element post-parse.
    """
    return raw.replace(_TEI_XMLNS_DECL, b"")


def _delete_unused_elements(xml: etree._Element):
    """Simplify <l> elements to plain text."""
    for L in xml.iter("l"):
        for note in L.findall("note"):
            L.remove(note)
        tail = L.tail
        text = "".join(L.itertext()).replace("-", "")
        L.clear()
        L.text = text
        L.tail = tail


def _to_devanagari(xml: etree._Element):
    """Transliterate inline elements to Devanagari."""
    for el in xml.iter():
        if not isinstance(el.tag, str):
            continue
        if el.text:
            el.text = transliterate(el.text, Scheme.Iast, Scheme.Devanagari)
        if el.tail:
            el.tail = transliterate(el.tail, Scheme.Iast, Scheme.Devanagari)


def _validate_section(section: Section):
    """Raise an exception if the section seems malformed."""
    all_slugs = [x.slug for x in section.blocks]
    if len(set(all_slugs)) != len(section.blocks):
        slug_list = ", ".join(sorted(all_slugs))
        raise ValueError(f"Block slugs are not unique: {slug_list}")


def _create_section(xml: etree._Element, section_slug: str) -> Section:
    """Create a section with the given slug.

    :param xml: the `Element` corresponding to this section.
    """
    section = Section(slug=section_slug, blocks=[])
    block_number = 1
    for child in xml:
        # Skip these elements entirely.
        if child.tag in {"note", "del"}:
            continue

        # Rewrite <subtitle> to <title type="sub">
        if child.tag == "subtitle":
            child.tag = "title"
            child.set("type", "sub")

        if child.tag not in SUPPORTED_TAGS:
            raise ValueError(
                f"Unsupported tag <{child.tag}> in section '{section_slug}'. "
                f"Supported tags: {', '.join(sorted(SUPPORTED_TAGS))}"
            )
        block_slug = str(block_number)
        block_number += 1

        blob = _tostring(child)
        if section_slug == SINGLE_SECTION_SLUG:
            full_slug = block_slug
        else:
            full_slug = f"{section_slug}.{block_slug}"

        block = Block(slug=full_slug, blob=blob)
        section.blocks.append(block)

    _validate_section(section)
    return section


def _parse_sections(xml: etree._Element) -> list[Section]:
    body = xml.find("./text/body")
    _delete_unused_elements(xml)
    _to_devanagari(body)

    sections = []
    divs = body.findall("./div")
    if len(divs) == 1 and divs[0].get("n") == "all":
        # Single wrapper div with n="all" — unwrap its children.
        section = _create_section(divs[0], SINGLE_SECTION_SLUG)
        sections = [section]
    elif divs:
        # Text has one or more sections.
        for i, div in enumerate(divs):
            section_slug = str(i + 1)
            section = _create_section(div, section_slug)
            sections.append(section)
    else:
        # Text has exactly one section.
        section = _create_section(body, SINGLE_SECTION_SLUG)
        sections = [section]
    return sections


def parse_document(path: Path) -> Document:
    raw = path.read_bytes()
    raw = _strip_namespace_bytes(raw)
    xml = etree.fromstring(raw, _PARSER)

    header = xml.find("./teiHeader")
    if header is None:
        raise ValueError(
            f"No <teiHeader> element found in {path.name}. "
            f"Is this a valid TEI XML file?"
        )
    header_blob = _tostring(header)

    sections = _parse_sections(xml)
    if not sections:
        raise ValueError(
            f"No sections found in {path.name}. "
            f"Expected <div> elements inside <text><body>, "
            f"or content directly inside <body>."
        )

    return Document(header=header_blob, sections=sections)
