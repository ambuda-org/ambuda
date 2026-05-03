"""Utilities for structuring text."""

import copy
import dataclasses as dc
import defusedxml.ElementTree as DET
import re
import xml.etree.ElementTree as ET
from enum import StrEnum
from typing import Iterable

from ambuda import database as db
from ambuda.utils.xml_validation import (
    BlockType,
    InlineType,
    TEITag,
    ValidationResult,
    validate_proofing_xml,
)


# TODO:
# All numbers --> ignore
# Line break after "\d+ ||" and mark as verse
# scripts / macros
# directly type harvard kyoto?
# footnote (^\d+.)
# break apart multiple footnotes


def _inner_xml(el):
    buf = [el.text or ""]
    for child in el:
        buf.append(ET.tostring(child, encoding="unicode"))
    return "".join(buf)


@dc.dataclass
class ProofBlock:
    """A block of structured content from the proofreading environment."""

    #: The block's type (paragraph, verse, etc.)
    type: str
    #: The block payload.
    content: str

    # general attributes
    #: The block's language ("sa", "hi", etc.)
    lang: str | None = None
    #: The internal text ID this block corresponds to.
    #: (Examples: "mula", "anuvada", "commentary", etc.)
    text: str | None = None

    # content attributes (verse, paragraph, etc.)
    #: The block's ordering ID ("43", "1.1", etc.)
    n: str | None = None
    #: If true, merge this block into the next one (e.g. if a block spans
    #: multiple pages.)
    merge_next: bool = False

    # footnote attributes
    #: the symbol that represents this footnote, e.g. "1".
    mark: str | None = None


@dc.dataclass
class ProofPage:
    """A page of structured content from the proofing environment."""

    #: The page's database ID (for cross-referencing)
    id: int
    #: The page's blocks in order.
    blocks: list[ProofBlock]

    def _from_xml_string(content: str, page_id: int) -> "ProofPage":
        # To prevent XML-based attacks
        root = DET.fromstring(content)
        if root.tag != "page":
            raise ValueError("Invalid root tag name")

        blocks = []
        for el in root:
            block_type = el.tag
            el_content = _inner_xml(el)
            lang = el.get("lang", None)
            text = el.get("text", None)
            n = el.get("n", None)
            mark = el.get("mark", None)
            # Earlier versions had a typo "merge-text", so continue to support it until all old
            # projects are migrated off.
            merge_next = (
                el.get("merge-next", "false").lower() == "true"
                or el.get("merge-text", "false").lower() == "true"
            )

            blocks.append(
                ProofBlock(
                    type=block_type,
                    content=el_content,
                    lang=lang,
                    text=text,
                    n=n,
                    mark=mark,
                    merge_next=merge_next,
                )
            )

        return ProofPage(id=page_id, blocks=blocks)

    @staticmethod
    def from_revision(revision: db.Revision) -> "ProofPage":
        text = revision.content.strip()
        return ProofPage.from_content_and_page_id(text, revision.page_id)

    @staticmethod
    def from_content_and_page_id(text: str, page_id: int) -> "ProofPage":
        """Exposed for `def structuring_api`"""
        try:
            parsed = ProofPage._from_xml_string(text, page_id)
        except Exception:
            parsed = None

        # If parsing succeeded and produced blocks, we're done.
        if parsed is not None and parsed.blocks:
            return parsed

        if not text or not text.strip():
            return ProofPage(blocks=[], id=page_id)

        # Either the XML didn't parse, or it parsed but had no element children
        # (e.g., bare text inside <page>...</page>, common in pre-XML content).
        # Strip a top-level <page> wrapper if present, then split as plain text.
        inner = text
        try:
            root = DET.fromstring(text)
            if root.tag == "page":
                inner = _inner_xml(root)
        except Exception:
            pass

        blocks = split_plain_text_to_blocks(inner)
        return ProofPage(id=page_id, blocks=blocks)

    def to_xml_string(self) -> str:
        root = ET.Element("page")
        root.text = "\n"
        for block in self.blocks:
            el = ET.SubElement(root, block.type)
            content = block.content.strip().replace("&", "&amp;")
            try:
                temp_wrapper = DET.fromstring(f"<temp>{content}</temp>")
            except Exception:
                temp_wrapper = ET.Element("temp")
                temp_wrapper.text = content

            el.text = temp_wrapper.text
            for child in temp_wrapper:
                el.append(child)

            if block.lang:
                el.set("lang", block.lang)
            if block.text:
                el.set("text", block.text)
            if block.n:
                el.set("n", block.n)
            if block.mark:
                el.set("mark", block.mark)
            if block.merge_next:
                el.set("merge-next", "true")
            el.tail = "\n"
        return ET.tostring(root, encoding="unicode")


def _is_verse(text: str) -> bool:
    DANDA = "\u0964"
    DOUBLE_DANDA = "\u0965"
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    if len(lines) == 2:
        # 2 lines = 2 ardhas
        first_has_danda = DANDA in lines[0]
        second_has_double_danda = DOUBLE_DANDA in lines[1]
        return first_has_danda and second_has_double_danda

    elif len(lines) == 4:
        second_has_danda = DANDA in lines[1]
        fourth_has_double_danda = DOUBLE_DANDA in lines[3]
        return second_has_danda and fourth_has_double_danda

    else:
        return False


def split_plain_text_to_blocks(
    text: str,
    match_stage=False,
    match_speaker=False,
    match_chaya=False,
    ignore_non_devanagari=False,
) -> list[ProofBlock]:
    DANDA = "\u0964"
    DOUBLE_DANDA = "\u0965"
    """NOTE: used to restructure an existing page, ignoring newlines etc."""

    def _is_verse_danda(line: str) -> bool:
        return line.endswith(DANDA) and line.count(DANDA) == 1

    def _is_verse_double_danda(line: str) -> bool:
        return line.endswith(DOUBLE_DANDA) and line.count(DANDA) == 0

    # Step 1: split into blocks
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    ids = [None] * len(lines)
    types = {}
    id = 0
    for i, line in enumerate(lines):
        if match_speaker:
            if m := re.fullmatch(r"^(\S+\s*[-–])(.+)", line):
                # Speaker --> start of new block
                id += 1
                line = lines[i] = f"<speaker>{m.group(1)}</speaker>{m.group(2)}"
                ids[i] = id

        if match_stage:
            if m := re.match(r"(.*)(\(.*?\))(.*)", line):
                line = lines[i] = f"{m.group(1)}<stage>{m.group(2)}</stage>{m.group(3)}"
                if not m.group(1) and not m.group(3):
                    # Stage without other elements --> separate block
                    id += 1
                    ids[i] = id
                    id += 1
                    continue

        if re.fullmatch(r"[०-९]+", line) or (
            ignore_non_devanagari and re.fullmatch("[^\u0900-\u097f]*", line)
        ):
            # Ignore numbers and non-Devanagari
            id += 1
            ids[i] = id
            types[id] = "ignore"
            id += 1
        elif re.match(r"^[०-९]+\.", line):
            # Footnote
            id += 1
            types[id] = "footnote"
            for j in range(i, len(lines)):
                # Footnote
                ids[j] = id
            id += 1
        elif re.fullmatch(r"\(.*\)", line):
            id += 1
        elif _is_verse_double_danda(line):
            # Verse?
            if i > 0 and _is_verse_danda(lines[i - 1]):
                id += 1
                # two-line verse
                for j in (i, i - 1):
                    ids[j] = id
                    types[id] = "verse"
                id += 1
            elif (
                i >= 3
                and DANDA not in lines[i - 3]
                and _is_verse_danda(lines[i - 2])
                and DANDA not in lines[i - 1]
            ):
                id += 1
                # four-line verse
                for j in (i, i - 1, i - 2, i - 3):
                    ids[j] = id
                    types[id] = "verse"
                id += 1
            else:
                # Base case
                ids[i] = id
        else:
            # Base case
            ids[i] = id

    groups = {}
    for k, v in zip(ids, lines):
        groups.setdefault(k, []).append(v)

    # Step 2b: process each block.
    blocks = []
    for key, group in groups.items():
        type = types.get(key, "p")
        content = "\n".join(group)

        if match_chaya:
            pattern = r"(\[.*?\])"
            replacement = r"<chaya>\1</chaya>"
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        blocks.append(ProofBlock(type=type, content=content))

    return blocks


@dc.dataclass
class ProofProject:
    """A structured project from the proofreading environment."""

    pages: list[ProofPage]

    @staticmethod
    def from_revisions(revisions: list[db.Revision]) -> "ProofProject":
        """Create structured data from a project's latest revisions."""
        pages = []
        for revision in revisions:
            try:
                page = ProofPage._from_xml_string(revision.content, revision.page_id)
            except Exception as e:
                continue
            page.id = revision.page_id
            pages.append(page)
        return ProofProject(pages=pages)


def to_plain_text(pages: list[ProofPage]) -> str:
    """Export pages as plain text."""
    parts = []
    for page in pages:
        for block in page.blocks:
            if block.type == "ignore":
                continue
            if block.type == "verse":
                parts.append(block.content)
            elif block.type == "footnote":
                prefix = f"[^{block.mark}] " if block.mark else ""
                parts.append(prefix + block.content)
            else:
                # Join paragraph lines into flowing text
                parts.append(" ".join(block.content.split()))
    return "\n\n".join(parts)


def to_tei_xml(pages: list[ProofPage]) -> str:
    """Export pages as TEI XML."""
    buf = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<TEI xmlns="http://www.tei-c.org/ns/1.0">',
        "<text>",
        "<body>",
    ]
    for i, page in enumerate(pages):
        buf.append(f'<pb n="{i + 1}" />')
        for block in page.blocks:
            if block.type == "ignore":
                continue
            elif block.type == "verse":
                lines = [
                    line.strip() for line in block.content.split("\n") if line.strip()
                ]
                lg_lines = "\n".join(f"  <l>{line}</l>" for line in lines)
                buf.append(f"<lg>\n{lg_lines}\n</lg>")
            elif block.type == "footnote":
                buf.append(f"<note>{block.content}</note>")
            else:
                buf.append(f"<p>{block.content}</p>")
    buf.extend(["</body>", "</text>", "</TEI>"])
    return "\n".join(buf)


def detect_language(text: str) -> str:
    """Detect the text language with basic heuristics."""
    if not text or not text.strip():
        return "sa"

    devanagari_count = len(re.findall(r"[\u0900-\u097F]", text))
    latin_count = len(re.findall(r"[a-zA-Z]", text))

    # mostly latin --> mark as English
    if latin_count / len(text) > 0.90:
        return "en"

    tokens = set(text.split())

    hindi_markers = ["की", "में", "है", "हैं", "था", "थी", "थे", "नहीं", "और", "चाहिए"]
    if any(marker in tokens for marker in hindi_markers):
        return "hi"

    return "sa"
