"""Align word analysis data with its parent XML element."""

from dataclasses import dataclass
from typing import Iterator
from xml.etree import ElementTree as ET

from flask import url_for
from indic_transliteration import sanscript

from ambuda.seed.utils.sandhi_utils import AC
from ambuda.utils.cheda import Token
from ambuda.xml import transform, tei_xml


@dataclass
class Chunk:
    text: str
    tokens: list[Token]


@dataclass
class Blob:
    text: str
    chunks: list[Chunk]


def _iter_text_with_parent(xml) -> Iterator[tuple[str, ET.Element, str]]:
    """Like ET.itertext(), but also yield the containing element and text type."""
    tag = xml.tag
    if not isinstance(tag, str) and tag is not None:
        return
    t = xml.text
    if t:
        yield t, xml, "text"
    for e in xml:
        yield from _iter_text_with_parent(e)
        t = e.tail
        if t:
            yield t, e, "tail"


def num_vowels(s: str) -> int:
    return sum(1 for L in s if L in AC)


def _make_chunk_elems(chunks: list[Chunk]) -> list[ET.Element]:
    elems = []
    for chunk in chunks:
        elem = ET.Element("s-chunk")

        tokens = []
        for token in chunk.tokens:
            token_el = ET.Element("s-w")

            # TODO: add a_el for non-JS?

            token_el.text = token.form
            token_el.attrib = {
                "lemma": token.lemma,
                "parse": token.parse,
            }
            if token.is_compounded:
                token_el.tail = "-"
            else:
                token_el.tail = " "
            tokens.append(token_el)

        elem[:] = tokens
        if not tokens:
            # Preserve punctuation.
            elem.text = chunk.text
            elem.attrib["type"] = "punct"
        elem.tail = " "

        elems.append(elem)
    return elems


def get_padas_for_text(text: str, iter_tokens: Iterator) -> list[Chunk]:
    chunks = []
    for chunk_text in text.split():
        num_chunk_vowels = num_vowels(chunk_text)
        chunk_tokens = []

        # The chunk "dharmakSetre" has the two tokens "dharma" and "kSetre".
        num_token_vowels = 0
        while num_token_vowels < num_chunk_vowels:
            token = next(iter_tokens)
            chunk_tokens.append(token)

            num_token_vowels += num_vowels(token.form)

            try:
                first = chunk_tokens[-2].form[-1]
                second = chunk_tokens[-1].form[0]
                if first in "aAiIuUfFxX" and second in AC:
                    num_token_vowels -= 1
                elif first in "eo" and second == "a":
                    num_token_vowels -= 1
            except IndexError:
                pass

        chunks.append(Chunk(text=chunk_text, tokens=chunk_tokens))
    return chunks


def transliterate_text_to(xml, source, dest):
    for el in xml.iter("*"):
        if el.attrib.get("lang") == "en":
            continue
        if el.text:
            el.text = sanscript.transliterate(el.text, source, dest)
        # Ignore xml.tail, since it's not within `xml`.
        if el.tail and el is not xml:
            el.tail = sanscript.transliterate(el.tail, source, dest)


def create_backup_parse(tokens: list[Token]) -> str:
    div = ET.Element("s-lg")
    div.attrib["class"] = "bg-red-100 p-2"
    for token in tokens:
        t = ET.Element("s-w")
        t.text = token.form
        t.attrib = {
            "lemma": token.lemma,
            "parse": token.parse,
        }
        if token.is_compounded:
            t.tail = "-"
        else:
            t.tail = " "
        div.append(t)
    transliterate_text_to(div, sanscript.SLP1, sanscript.DEVANAGARI)

    explain = ET.Element("p")
    explain.attrib["class"] = "mb-2 text-sm"
    explain.attrib["lang"] = "en"
    explain.text = "This analysis has one or more issues. Use with caution:"
    div.insert(0, explain)
    return div


def insert_link(xml, href):
    a = ET.Element("a")
    a.attrib["class"] = "text-sm text-zinc-400 hover:underline js--source"
    a.attrib["href"] = href
    a.text = "Show original"
    xml.append(a)


def align_text_with_parse(
    xml_blob: str, tokens: list[Token], text_slug, block_slug
) -> ET.Element:
    """Align text and parse data by storing parse data on its source XML blob."""
    iter_tokens = iter(tokens)

    xml = ET.fromstring(xml_blob)
    transliterate_text_to(xml, sanscript.DEVANAGARI, sanscript.SLP1)

    # In-order traversal of XML text nodes
    for text, el, attr in list(_iter_text_with_parent(xml)):
        text = text.strip()
        if not text:
            continue

        # The text "dharmakSetre kurukSetre" has the two chunks "dharmakSetre" and
        # "kurukSetre".
        try:
            chunks = get_padas_for_text(text, iter_tokens)
        except StopIteration:
            # Doesn't line up -- bail out with a lower quality but still usable
            # parse.
            xml = create_backup_parse(tokens)
            break

        # Modify source XML with the aligned token data.
        chunk_elems = _make_chunk_elems(chunks)
        if attr == "text":
            el.text = None
            el[:] = chunk_elems + el[:]
        else:
            el.tail = None
            el[:] += chunk_elems

    transliterate_text_to(xml, sanscript.SLP1, sanscript.DEVANAGARI)
    source_url = url_for("api.block_htmx", text_slug=text_slug, block_slug=block_slug)
    insert_link(xml, source_url)
    return transform(xml, tei_xml)
