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
from xml.etree import ElementTree as ET

from indic_transliteration import sanscript

#: Most texts have multiple sections and use section slugs like "1", "2", etc.
#: If a text has just one section, we create a single "default" section with
#: the slug "all".
SINGLE_SECTION_SLUG = "all"
#: Tags that we support on our display. If a section contains a tag that's not
#: in this list, the code below will raise an error.
SUPPORTED_TAGS = {"lg", "head", "p", "trailer", "milestone", "pb"}
#: Minimal namespace mapping for TEI documents.
NS = {
    "xml": "{http://www.w3.org/XML/1998/namespace}",
    "tei": "{http://www.tei-c.org/ns/1.0}",
}


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


def _remove_namespace(xml: ET.Element, prefix: str):
    """Remove the given namespace prefix from all elements.

    ElementTree expands tidy namespaced names like "xml:id" into names like
    "{http://www.w3.org/XML/1998/namespace}id", which are less usable. This
    function removes these namespaces so that downstream code can be more
    readable.
    """
    for el in xml.iter("*"):
        if el.tag.startswith(prefix):
            el.tag = el.tag[len(prefix) :]


def _delete_unused_elements(xml: ET.Element):
    """Remove unused elements in-place."""
    for L in xml.iter("l"):
        for el in L:
            # Delete tag but keep text.
            # - `<seg>`: a arbitrary segment, usually representing a pāda.
            # - `<hi>`: highlighted text, e.g. bold text.
            if el.tag in {"seg", "hi"}:
                el.tag = None
            # Delete tag and text.
            # - `<note>`: comments by the document editors.
            if el.tag in {"note"}:
                el.tag = None
                el.clear()

        text = "".join(L.itertext())
        text = text.replace("-", "")
        L.clear()
        L.text = text


def _to_devanagari(xml: ET.Element):
    """Transliterate inline elements to Devanagari."""
    t = sanscript.transliterate
    for el in xml.iter("*"):
        if el.text:
            el.text = t(el.text, sanscript.IAST, sanscript.DEVANAGARI)
        if el.tail:
            el.tail = t(el.tail, sanscript.IAST, sanscript.DEVANAGARI)


def _validate_section(section: Section):
    """Raise an exception if the section seems malformed."""
    all_slugs = [x.slug for x in section.blocks]
    if len(set(all_slugs)) != len(section.blocks):
        slug_list = ", ".join(sorted(all_slugs))
        raise ValueError(f"Block slugs are not unique: {slug_list}")


def _create_section(xml: ET.Element, section_slug: str) -> Section:
    """Create a section with the given slug.

    :param xml: the `Element` corresponding to this section.
    """
    section = Section(slug=section_slug, blocks=[])
    block_number = 1
    for child in xml:
        # Skip these elements entirely.
        if child.tag in {"note", "del"}:
            continue

        assert child.tag in SUPPORTED_TAGS, child.tag
        if child.tag == "head":
            block_slug = "head"
        else:
            block_slug = str(block_number)
            block_number += 1

        blob = ET.tostring(child, encoding="utf-8").decode("utf-8")
        if section_slug == SINGLE_SECTION_SLUG:
            full_slug = block_slug
        else:
            full_slug = f"{section_slug}.{block_slug}"

        block = Block(slug=full_slug, blob=blob)
        section.blocks.append(block)

    _validate_section(section)
    return section


def _parse_sections(xml: ET.Element) -> list[Section]:
    body = xml.find("./text/body")
    _delete_unused_elements(xml)
    _to_devanagari(body)

    sections = []
    divs = body.findall("./div")
    if divs:
        # Text has one or more sections.
        for i, div in enumerate(body.findall("./div")):
            section_slug = str(i + 1)
            section = _create_section(div, section_slug)
            sections.append(section)
    else:
        # Text has exactly one section.
        section = _create_section(body, SINGLE_SECTION_SLUG)
        sections = [section]
    return sections


def parse_document(path: Path) -> Document:
    xml = ET.parse(path).getroot()
    _remove_namespace(xml, NS["tei"])

    header = xml.find("./teiHeader")
    assert header
    header_blob = ET.tostring(header, encoding="utf-8").decode("utf-8")

    sections = _parse_sections(xml)
    assert sections

    return Document(header=header_blob, sections=sections)
