"""Converts a proofread project into a published text.

Structuring has four phases:

1. Select the project blocks that we want to assemble into a text.
2. Convert project XML to TEI XML, combining blocks if necessary.
3. Resolve block numbers, footnotes, and other references.
4. Write to disk, using the project as a source of metadata.
"""

import copy
import dataclasses as dc
from collections import Counter
from datetime import date
import re
from lxml import etree
from pathlib import Path
from typing import Iterable

from sqlalchemy import select, func

from ambuda import database as db
from ambuda.consts import SINGLE_SECTION_SLUG
from ambuda.enums import SitePageStatus
from ambuda.utils.project_structuring import ProofPage
from ambuda.utils import project_utils
from ambuda import queries as q
from ambuda.utils.xml import indent_xml_file_in_place
from ambuda.utils.xml_validation import (
    BlockType,
    InlineType,
    TEITag,
)


# Placeholder for <pb> elements where the page number can't be resolved.
DEFAULT_PRINT_PAGE_NUMBER = "-"
# Default XML namespace
_XML_NS = "http://www.w3.org/XML/1998/namespace"
# lxml parser with basic security protections (XXE, billion-laughs)
_SAFE_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


@dc.dataclass
class IndexedBlock:
    """A block of proofing XML, as seen during iteration."""

    # The revision this block comes from.
    revision: db.Revision
    # 1-indexed image number (for resolving page numbers)
    image_number: int
    # 0-indexed block index within the page
    block_index: int
    # the raw page XML
    page_xml: etree._Element


@dc.dataclass
class TEIBlock:
    """A structured block in TEI XML (publication-ready)."""

    xml: str
    slug: str
    page_id: int


@dc.dataclass
class TEISection:
    """A structured block section in TEI XML (publication-ready)."""

    slug: str
    blocks: list[TEIBlock]


@dc.dataclass
class TEIDocument:
    """A parsed TEI document (publication-ready)."""

    #: The TEI header as an XML blob with namespaces stripped.
    header: str
    #: TEI sections in order.
    sections: list[TEISection]


@dc.dataclass
class TEIRewrite:
    # A mix of sections and blocks.
    items: list[TEISection | TEIBlock]
    errors: list[str]
    # Histogram of page statuses
    page_statuses: Counter


def _safe_fromstring(text: str | bytes) -> etree._Element:
    """Parse an XML string safely."""
    if isinstance(text, str):
        text = text.encode("utf-8")
    return etree.fromstring(text, _SAFE_PARSER)


def _to_string(el: etree._Element) -> str:
    """Serialize an element to a Unicode string with readable self-closing tags."""
    s = etree.tostring(el, encoding="unicode")
    # I tried getting lxml to output this directly but didn't succeed.
    # This will cause problems if we store /> in strings, etc. but we never do this.
    return re.sub(r"(?<! )/>", " />", s)


class Filter:
    """Selects a project's blocks based on the given condition (`sexp`).

    Options:
    - `image` -- matches a range of image numberS
    - `label` -- matches blocks by label
    - `tag` -- matches blocks by tag (p, verse, ...)
    - `and` -- logical AND of multiple conditions
    - `or` -- logical OR of multiple conditions
    - `not` -- logical NOT of a condition
    """

    def __init__(self, sexp: str):
        """Initializes the filter. Raises a `ValueError` if `sexp` is invalid."""
        sexp = sexp.strip()
        if not sexp:
            return []
        if not sexp.startswith("("):
            raise ValueError("S-expression must start with '('")

        i = 0

        def parse_list(depth=0):
            # Arbitrary depths are fine, but in practice nothing is deeper than 5 levels.
            _MAX_DEPTH = 5
            if depth > _MAX_DEPTH:
                raise ValueError(f"Filter is more than {_MAX_DEPTH} levels deep")

            nonlocal i
            result = []
            i += 1

            while i < len(sexp):
                while i < len(sexp) and sexp[i].isspace():
                    i += 1

                if i >= len(sexp):
                    raise ValueError("Unexpected end of input")

                if sexp[i] == ")":
                    i += 1
                    return result
                elif sexp[i] == "(":
                    result.append(parse_list(depth + 1))
                else:
                    atom_start = i
                    while i < len(sexp) and sexp[i] not in "() \t\n\r":
                        i += 1
                    atom = sexp[atom_start:i]
                    result.append(atom)
            raise ValueError("Missing closing parenthesis")

        self.predicate = parse_list()

    @staticmethod
    def _parse_image_spec(spec: str) -> tuple[int, str | None]:
        if ":" in spec:
            num, label = spec.split(":", 1)
            return int(num), label
        else:
            return int(spec), None

    @staticmethod
    def _find_label_index(page_xml, label: str) -> int | None:
        for i, el in enumerate(page_xml):
            if el.attrib.get("text") == label:
                return i
        return None

    def image_range(self) -> tuple[int, int] | None:
        """Extract the image range from the filter, if it's a simple image filter.

        Returns (min_image, max_image) if the filter is a simple image/page
        predicate (possibly combined with ``and``). Returns ``None`` for
        non-image filters or complex boolean combinations where we cannot
        safely narrow the range.
        """

        def _range(sexp) -> tuple[int, int] | None:
            try:
                key = sexp[0]
            except (IndexError, TypeError):
                return None

            if key in ("image", "page"):
                start, _ = self._parse_image_spec(sexp[1])
                try:
                    end, _ = self._parse_image_spec(sexp[2])
                except IndexError:
                    end = start
                return (start, end)

            if key == "and":
                lo, hi = 1, float("inf")
                for child in sexp[1:]:
                    r = _range(child)
                    if r is not None:
                        lo = max(lo, r[0])
                        hi = min(hi, r[1])
                if hi == float("inf"):
                    return None
                return (lo, int(hi))

            return None

        return _range(self.predicate)

    def matches(self, block: IndexedBlock) -> bool:
        """Return whether `block` matches this filter's condition.

        If the filter is misconfigured, return `False`.
        """

        def _matches(sexp):
            try:
                key = sexp[0]
                if key == "image" or key == "page":
                    start_image, start_label = Filter._parse_image_spec(sexp[1])
                    try:
                        end_image, end_label = Filter._parse_image_spec(sexp[2])
                    except IndexError:
                        end_image, end_label = start_image, start_label

                    if (
                        block.image_number < start_image
                        or block.image_number > end_image
                    ):
                        return False

                    if block.image_number == start_image and start_label is not None:
                        idx = Filter._find_label_index(block.page_xml, start_label)
                        if idx is None or block.block_index < idx:
                            return False

                    if block.image_number == end_image and end_label is not None:
                        idx = Filter._find_label_index(block.page_xml, end_label)
                        if idx is None or block.block_index > idx:
                            return False

                    return True
                if key == "label":
                    return (
                        block.page_xml[block.block_index].attrib.get("text") == sexp[1]
                    )
                if key == "tag":
                    return block.page_xml[block.block_index].tag == sexp[1]

                if key == "and":
                    return all(_matches(x) for x in sexp[1:])
                if key == "or":
                    return any(_matches(x) for x in sexp[1:])
                if key == "not":
                    return not _matches(sexp[1])
            except Exception as e:
                return False

        return _matches(self.predicate)


@dc.dataclass
class UncoveredBlock:
    """A block not matched by any publish config filter."""

    page_slug: str
    image_number: int
    block_index: int
    block_tag: str
    block_text: str


def find_uncovered_blocks(project: db.Project) -> list[UncoveredBlock]:
    """Find all blocks not matched by any publish config's target filter.

    (Skips 'ignore' and 'metadata' blocks.)
    """

    publish_configs = sorted(project.publish_configs, key=lambda c: c.order)

    if not publish_configs:
        return []

    # Build filters from all publish configs
    filters: list[Filter] = []
    for pc in publish_configs:
        target = pc.target or ""
        try:
            if target.startswith("("):
                filters.append(Filter(target))
            elif target:
                filters.append(Filter(f"(label {target})"))
            # Empty target matches everything — no uncovered blocks possible
            else:
                return []
        except ValueError:
            continue

    if not filters:
        return []

    # Load latest revisions
    session = q.get_session()
    subq = (
        select(db.Revision.page_id, func.max(db.Revision.id).label("max_id"))
        .where(db.Revision.project_id == project.id)
        .group_by(db.Revision.page_id)
        .subquery()
    )
    revisions = (
        session.execute(
            select(db.Revision)
            .join(subq, db.Revision.id == subq.c.max_id)
            .join(db.Page, db.Revision.page_id == db.Page.id)
            .order_by(db.Page.order)
        )
        .scalars()
        .all()
    )

    skip_page_ids = {
        page.id for page in project.pages if page.status.name == SitePageStatus.SKIP
    }
    page_id_to_slug = {page.id: page.slug for page in project.pages}
    page_id_to_image_number = {page.id: i + 1 for i, page in enumerate(project.pages)}

    uncovered: list[UncoveredBlock] = []
    for revision in revisions:
        if revision.page_id in skip_page_ids:
            continue
        image_number = page_id_to_image_number.get(revision.page_id)
        if image_number is None:
            continue

        page_text = revision.content
        try:
            page_xml = _safe_fromstring(page_text)
        except etree.XMLSyntaxError:
            continue

        page_slug = page_id_to_slug.get(revision.page_id, "?")

        for block_index, block_el in enumerate(page_xml):
            tag = block_el.tag
            if tag in (BlockType.IGNORE, BlockType.METADATA):
                continue

            ib = IndexedBlock(revision, image_number, block_index, page_xml)
            if not any(f.matches(ib) for f in filters):
                text = (block_el.text or "").strip()
                if text:
                    text = text[:80] + ("..." if len(text) > 80 else "")
                uncovered.append(
                    UncoveredBlock(page_slug, image_number, block_index, tag, text)
                )

    return uncovered


# TODO:
# - keep <l>-final "-" and mark as appropriate elem
# x concatenate within <sp> for speaker
#   - when building, reshape to partial "<sp>" for continuity
# - build footnote refs and check them with warnings
#   - <ref target="#X"> type="noteAnchor">
#   - <note xml:id="X" type="footnote">...</note>
def _split_block_at_breaks(xml: etree._Element) -> list[etree._Element]:
    """Split a block element at <break/> markers, returning sub-blocks.

    If there are no <break/> children, returns a single-element list
    containing the original element (unmodified).
    """
    break_children = [child for child in xml if child.tag == InlineType.BREAK]
    if not break_children:
        return [xml]

    sub_blocks: list[etree._Element] = []
    current = etree.Element(xml.tag, dict(xml.attrib))
    current.text = xml.text or ""

    for child in list(xml):
        if child.tag == InlineType.BREAK:
            sub_blocks.append(current)
            current = etree.Element(xml.tag, dict(xml.attrib))
            current.attrib.pop("n", None)
            current.text = child.tail or ""
        else:
            current.append(child)
            # If there's tail text after the child, it's already on child.tail
            # and will move with the child — no extra handling needed.

    sub_blocks.append(current)
    return sub_blocks


def _trim_children(xml: etree._Element):
    # Trim left
    xml.text = (xml.text or "").lstrip()
    # Trim right -- depends on if there are child elements
    if len(xml):
        xml[-1].tail = (xml[-1].tail or "").rstrip()
    else:
        xml.text = (xml.text or "").rstrip()


def _rewrite_block_to_tei_xml(xml: etree._Element, image_number: int):
    """Rewrite a block of proofing XML into TEI XML."""

    maybe_n = xml.attrib.get("n")
    xml.attrib.clear()

    # Inline elements
    for el in xml.iter():
        if el.tag == InlineType.STAGE:
            # Remove () for stage directions
            text = (el.text or "").strip()
            normed_text = re.sub(r"\(\s*(.*?)\s*\)", r"\1", text)
            if text != normed_text:
                el.attrib["rend"] = "parentheses"
            el.text = normed_text.strip()
            # add whitespace before following element
            if el.tail and el.tail[0] != " ":
                el.tail = " " + el.tail
        elif el.tag == InlineType.SPEAKER:
            # Remove trailing "-" for speakers
            text = el.text or ""
            normed_text = re.sub(r"(.*?)\s*[-–]+\s*$", r"\1", text)
            if text != normed_text:
                el.attrib["rend"] = "dash"
            el.text = normed_text.strip()
        elif el.tag == InlineType.CHAYA:
            # Remove surrounding [ ] brackets.
            text = (el.text or "").strip()
            normed_text = re.sub(r"^\[\s*(.*)\s*\]", r"\1", text)
            if text != normed_text:
                el.attrib["rend"] = "brackets"
            el.text = normed_text.strip()
        elif el.tag == BlockType.VERSE:
            # Add consistent spacing around double dandas.
            text = (el.text or "").strip()
            text = re.sub(r"\s*॥\s*", " ॥ ", text)
            text = re.sub(r"॥ $", "॥", text)
            el.text = text
        elif el.tag == "ref":
            # Assign a temporary id for cross-referencing later.
            el.attrib["type"] = "noteAnchor"
            el.attrib["target"] = f"{image_number}.{el.text or ''}"
        elif el.tag == "flag":
            el.tag = "unclear"
        elif el.tag in (InlineType.ADD, InlineType.ELLIPSIS):
            pass
        elif el.tag == InlineType.DELETE:
            el.tag = "del"

    # <speaker>
    try:
        speaker = next(x for x in xml if x.tag == InlineType.SPEAKER)
    except StopIteration:
        speaker = None
    if speaker is not None:
        old_tag = xml.tag
        old_children = [x for x in xml if x.tag != InlineType.SPEAKER]

        speaker_tail = speaker.tail or ""
        speaker.tail = ""

        xml.clear()
        xml.tag = "sp"
        xml.append(speaker)
        if not old_children and not speaker_tail.strip():
            # Special case: <p> contains only speaker, so don't create a child elem.
            return

        child = etree.SubElement(xml, old_tag)
        child.text = (speaker_tail + (xml[-1].text or "")).strip()
        child.extend(old_children)
        _rewrite_block_to_tei_xml(child, image_number)
        # Can lose other attrs, but must preserve n if present.
        if maybe_n:
            child.attrib["n"] = maybe_n
        return

    # <error> and <fix>
    i = 0
    while i < len(xml):
        el = xml[i]
        el_tail = (el.tail or "").strip()
        if el.tag not in ("error", "fix"):
            i += 1
            continue

        # Standardize order: <error> then <fix>
        if i + 1 < len(xml):
            el_next = xml[i + 1]
            if (el.tag, el_next.tag) == ("fix", "error") and not el_tail:
                # Normalize to avoid weird errors later.
                el.tail = ""
                xml.remove(el)
                xml.remove(el_next)
                xml.insert(i, el_next)
                xml.insert(i + 1, el)

        # Reload since `el` may be stale after swap.
        el = xml[i]
        if el.tag == "error":
            error = xml[i]
            has_counterpart = i + 1 < len(xml) and not el_tail
            maybe_fix = xml[i + 1] if has_counterpart else None

            choice = etree.Element("choice")
            sic = etree.SubElement(choice, "sic")
            sic.text = el.text or ""
            corr = etree.SubElement(choice, "corr")
            if maybe_fix is not None:
                corr.text = maybe_fix.text or ""
                choice.tail = maybe_fix.tail
                del xml[i + 1]
            else:
                choice.tail = error.tail
            del xml[i]

            xml.insert(i, choice)
        elif el.tag == "fix":
            # Edge case: <fix> without <error> is renamed to <supplied>.
            el.tag = "supplied"

        i += 1

    # <del> and <add> --> <subst>
    i = 0
    while i < len(xml):
        el = xml[i]
        el_tail = (el.tail or "").strip()
        if el.tag not in ("del", "add"):
            i += 1
            continue

        # Standardize order: <del> then <add>
        if i + 1 < len(xml):
            el_next = xml[i + 1]
            if (el.tag, el_next.tag) == ("add", "del") and not el_tail:
                el.tail = ""
                xml.remove(el)
                xml.remove(el_next)
                xml.insert(i, el_next)
                xml.insert(i + 1, el)

        el = xml[i]
        if el.tag == "del":
            has_counterpart = i + 1 < len(xml) and not el_tail
            maybe_add = xml[i + 1] if has_counterpart else None

            if maybe_add is not None and maybe_add.tag == "add":
                subst = etree.Element("subst")
                del_el = etree.SubElement(subst, "del")
                del_el.text = el.text or ""
                add_el = etree.SubElement(subst, "add")
                add_el.text = maybe_add.text or ""
                subst.tail = maybe_add.tail
                del xml[i + 1]
                del xml[i]
                xml.insert(i, subst)
            # Lone <del> stays as-is.

        i += 1

    if xml.tag == BlockType.VERSE:
        xml.tag = TEITag.LG
    elif xml.tag == BlockType.HEADING:
        xml.tag = TEITag.HEAD
        _trim_children(xml)
    elif xml.tag in {BlockType.TRAILER, BlockType.TITLE}:
        _trim_children(xml)
    elif xml.tag == BlockType.SUBTITLE:
        xml.tag = TEITag.TITLE
        xml.attrib["type"] = "sub"
        _trim_children(xml)
    elif xml.tag == BlockType.FOOTNOTE:
        xml.tag = TEITag.NOTE
        xml.attrib["type"] = "footnote"

    # <p> text normalization
    if xml.tag == "p":

        def _normalize_text(xml):
            if xml.text is not None:
                xml.text = re.sub(r"-\n", "", xml.text, flags=re.M)
                xml.text = re.sub(r"\s+", " ", xml.text, flags=re.M)
            if xml.tail is not None:
                xml.tail = re.sub(r"-\n", "", xml.tail, flags=re.M)
                xml.tail = re.sub(r"\s+", " ", xml.tail, flags=re.M)
            for el in xml:
                _normalize_text(el)

        _normalize_text(xml)

        # <chaya> is currently supported only for <p> elements.
        # TODO: migrate existing text to explicit prakrit / chaya
        try:
            chaya = next(x for x in xml if x.tag == "chaya")
        except StopIteration:
            chaya = None
        if chaya is not None:
            choice = etree.Element(TEITag.CHOICE)
            choice.attrib["type"] = "chaya"

            prakrit = etree.SubElement(choice, "seg")
            prakrit.attrib[f"{{{_XML_NS}}}lang"] = "pra"
            prakrit.text = xml.text
            prakrit.extend(x for x in xml if x.tag != "chaya")

            sanskrit = etree.SubElement(choice, "seg")
            sanskrit.attrib[f"{{{_XML_NS}}}lang"] = "sa"
            if "rend" in chaya.attrib:
                sanskrit.attrib["rend"] = chaya.attrib["rend"]
            sanskrit.text = chaya.text
            sanskrit.extend(chaya)

            xml.text = ""
            del xml[:]
            xml.append(choice)

    # <verse> line splitting
    if xml.tag == "lg":
        lines = []
        for fragment in (xml.text or "").strip().splitlines():
            line = etree.Element("l")
            line.text = fragment
            lines.append(line)

        for el in xml:
            if not lines:
                lines.append(etree.Element("l"))
            lines[-1].append(el)
            for i, fragment in enumerate((el.tail or "").splitlines()):
                if i == 0:
                    el.tail = fragment.strip()
                else:
                    lines.append(etree.Element("l"))
                    lines[-1].text = fragment.strip()

        xml.text = ""
        xml.clear()
        xml.extend(lines)

    if maybe_n:
        xml.attrib["n"] = maybe_n


def _concatenate_tei_xml_blocks_across_page_boundary(
    first: etree._Element, second: etree._Element, page_number: str
):
    """Concatenate two blocks of TEI XML by updating the first block in-place.

    Use case: merging blocks across page breaks.
    """
    if first.tag == "sp":
        # Special case for <sp>: concatenate children, leaving speaker alone.
        assert len(first) >= 2
        _concatenate_tei_xml_blocks_across_page_boundary(first[-1], second, page_number)
        return

    pb = etree.SubElement(first, "pb")
    pb.attrib["n"] = page_number

    if first.tag in {"p", "lg"}:
        pb.tail = second.text or ""
    first.extend(second)


class NCounter:
    """Manages the `n` value across different types of blocks in a text."""

    def __init__(self):
        self.prefix = None
        self.block_ns = {}

    def set_prefix(self, prefix: str):
        self.prefix = prefix
        self.block_ns = {}

    def override(self, tag: str, n: str):
        self.block_ns[tag] = n

    def next(self, tag: str) -> str:
        if tag in self.block_ns:
            # Increment
            prev_n = self.block_ns[tag]
            if m := re.search(r"(.*?)(\d+)$", prev_n):
                n = f"{m.group(1)}{int(m.group(2)) + 1}"
            else:
                n = prev_n + "2"
        else:
            if self.prefix:
                n = f"{self.prefix}.{tag}1"
            else:
                n = f"{tag}1"
        self.block_ns[tag] = n
        return n

    @staticmethod
    def _counter_key(tei_xml: etree._Element) -> str:
        if tei_xml.tag == "title" and tei_xml.get("type") == "sub":
            return "subtitle"
        return tei_xml.tag

    def maybe_assign_n(self, explicit_n: str | None, tei_xml: etree._Element):
        key = self._counter_key(tei_xml)
        if tei_xml.tag in {"note", "sp", InlineType.SPEAKER}:
            # Do nothing -- these elements should never have an "n" assigned.
            pass
        elif explicit_n:
            self.override(key, explicit_n)
            tei_xml.attrib["n"] = explicit_n
        else:
            n = self.next(key)
            tei_xml.attrib["n"] = n

            if tei_xml.tag == "sp":
                # Don't number <sp>, but do number its children.
                for child_xml in tei_xml:
                    # child may have an explicit n, which we should reuse
                    self.maybe_assign_n(child_xml.attrib.get("n"), child_xml)


def _rewrite_project_to_tei_xml(
    project: db.Project,
    config: db.PublishConfig,
    revisions: list[db.Revision],
) -> TEIRewrite:
    """Create TEI sections and blocks from a project."""
    rules = project_utils.parse_page_number_spec(project.page_numbers)
    page_numbers = project_utils.apply_rules(len(project.pages), rules)

    # Map page_id -> 1-based image number (visual position) so that
    # pages with no revisions don't shift subsequent image numbers.
    page_id_to_image_number = {page.id: i + 1 for i, page in enumerate(project.pages)}

    target = config.target or ""
    if target.startswith("("):
        block_filter = Filter(target)
    else:
        # Legacy behavior.
        block_filter = Filter(f"(label {target})")
    img_range = block_filter.image_range()

    page_statuses = Counter()

    def _iter_blocks(revisions) -> Iterable[IndexedBlock]:
        """Iterate over all blocks in the given revisions."""
        nonlocal page_statuses
        for revision in revisions:
            image_number = page_id_to_image_number.get(revision.page_id)
            if image_number is None:
                continue
            if img_range and (
                image_number < img_range[0] or image_number > img_range[1]
            ):
                continue

            page_text = revision.content
            page_statuses[revision.status.name] += 1
            try:
                page_xml = _safe_fromstring(page_text)
            except etree.XMLSyntaxError:
                page_struct = ProofPage.from_content_and_page_id(page_text, 0)
                page_xml_str = page_struct.to_xml_string()
                page_xml = _safe_fromstring(page_xml_str)

            for block_index, block in enumerate(page_xml):
                yield IndexedBlock(revision, image_number, block_index, page_xml)

    def _iter_filtered_blocks(revisions) -> Iterable[IndexedBlock]:
        """Iterate over all blocks that match this config's filter."""
        for block in _iter_blocks(revisions):
            block_xml = block.page_xml[block.block_index]
            if block_xml.tag == BlockType.IGNORE:
                # Always skip "ignore" blocks.
                continue

            if block_filter.matches(block):
                yield block

    def _parse_metadata(text: str) -> dict[str, str]:
        ret = {}
        for line in text.splitlines():
            key, value = line.split("=")
            key = key.strip()
            value = value.strip()
            ret[key] = value
        return ret

    @dc.dataclass
    class Fragment:
        xml: etree._Element
        merge_next: bool

    def _iter_raw_fragments(revisions):
        """Iterate over raw TEI fragments, along with other control flow data."""
        cur_page_id = None
        for block in _iter_filtered_blocks(revisions):
            # <pb> elements
            page_id = block.revision.page_id
            if page_id != cur_page_id:
                yield ("page", page_id)
                cur_page_id = page_id

            proof_xml = block.page_xml[block.block_index]

            # Metadata (ingestion controls)
            if proof_xml.tag == BlockType.METADATA:
                # `metadata` contains special commands for this function.
                data = _parse_metadata(proof_xml.text or "")
                yield ("metadata", data)
                continue

            # XML blocks
            proof_copy = copy.deepcopy(proof_xml)
            sub_blocks = _split_block_at_breaks(proof_copy)
            merge_next = (
                proof_xml.get("merge-next", "false").lower() == "true"
                or proof_xml.get("merge-text", "false").lower() == "true"
            )
            for i, sub_block_xml in enumerate(sub_blocks):
                tei_xml = sub_block_xml
                _rewrite_block_to_tei_xml(tei_xml, block.image_number)
                yield (
                    "xml",
                    Fragment(
                        xml=tei_xml,
                        merge_next=merge_next,
                    ),
                )

    n_to_page_id = {}
    n_overrides = set()
    TOPLEVEL = "__toplevel"

    def _iter_stitched_xml(revisions) -> Iterable[etree._Element]:
        """Iterate over stitched TEI fragments."""

        nonlocal n_to_page_id, n_overrides

        div = etree.Element("div")
        div.attrib[TOPLEVEL] = "_"
        sp = None
        merges: dict[str, etree._Element] = {}

        ns = NCounter()
        cur_page_id = None
        for f_type, data in _iter_raw_fragments(revisions):
            if f_type == "metadata":
                if "div.n" in data:
                    # Handle old state
                    yield div

                    div_n = data["div.n"]
                    ns.set_prefix(div_n)
                    div = etree.Element("div")
                    div.attrib["n"] = div_n
                elif "speaker" in data:
                    if not data["speaker"]:
                        sp = None

            elif f_type == "page":
                cur_page_id = data

            elif f_type == "xml":
                assert cur_page_id is not None

                xml = data.xml

                # merge_next -- concatenate blocks as needed.
                if merges.get(xml.tag) is not None or merges.get("sp") is not None:
                    key = xml.tag if merges.get(xml.tag) is not None else "sp"
                    first = merges[key]
                    page_number = page_numbers[page_id_to_image_number[cur_page_id] - 1]
                    _concatenate_tei_xml_blocks_across_page_boundary(
                        first, xml, page_number
                    )

                    if not data.merge_next:
                        del merges[key]
                    continue
                else:
                    merges[xml.tag] = data.xml if data.merge_next else None

                # @n -- populate from `ns` counter if not set manually.
                counter_key = NCounter._counter_key(xml)
                if "n" in xml.attrib:
                    n = xml.attrib["n"]
                    ns.override(counter_key, n)
                    n_overrides.add(n)
                else:
                    xml.attrib["n"] = ns.next(counter_key)

                # n -> page_id mapping
                n_to_page_id[xml.attrib["n"]] = cur_page_id

                if sp is not None:
                    sp.append(xml)
                else:
                    div.append(xml)

                if xml.tag == "sp":
                    sp = xml

        yield div

    def _sanitize_ns(divs: list[etree._Element]):
        nonlocal n_to_page_id
        # Single head / trailer / title
        for div in divs:
            for singleton_tag in ("head", "trailer"):
                matches = div.findall(singleton_tag)
                if len(matches) == 1 and matches[0].get("n") not in n_overrides:
                    old_n = matches[0].get("n")
                    matches[0].set("n", singleton_tag)
                    if old_n in n_to_page_id:
                        n_to_page_id[singleton_tag] = n_to_page_id.pop(old_n)

            titles = div.findall("title")
            main_titles = [t for t in titles if t.get("type") != "sub"]
            if len(main_titles) == 1 and main_titles[0].get("n") not in n_overrides:
                title = main_titles[0]
                old_n = title.get("n")
                title.set("n", "title")
                if old_n in n_to_page_id:
                    n_to_page_id["title"] = n_to_page_id.pop(old_n)

            subtitles = [t for t in titles if t.get("type") == "sub"]
            if len(subtitles) == 1 and subtitles[0].get("n") not in n_overrides:
                subtitle = subtitles[0]
                old_n = subtitle.get("n")
                subtitle.set("n", "subtitle")
                if old_n in n_to_page_id:
                    n_to_page_id["subtitle"] = n_to_page_id.pop(old_n)

        # If no <p> in divisions, use "1" instead of "lg1", etc.
        has_p = any(div.find("p") is not None for div in divs)
        if not has_p:
            for div in divs:
                for lg in div.findall("lg"):
                    n = lg.get("n")
                    if n and n not in n_overrides:
                        new_n = n.replace("lg", "")
                        lg.set("n", new_n)
                        if n in n_to_page_id:
                            n_to_page_id[new_n] = n_to_page_id.pop(n)

    items = []
    divs = list(_iter_stitched_xml(revisions))
    _sanitize_ns(divs)
    for div in divs:
        if TOPLEVEL not in div.attrib:
            assert "n" in div.attrib

            blocks = []
            for child in div:
                assert "n" in child.attrib
                n = child.attrib["n"]
                assert n in n_to_page_id
                blocks.append(
                    TEIBlock(
                        xml=_to_string(child),
                        slug=n,
                        page_id=n_to_page_id[n],
                    )
                )

            section = TEISection(
                slug=div.attrib["n"],
                blocks=blocks,
            )
            items.append(section)
        else:
            for child in div:
                assert "n" in child.attrib
                n = child.attrib["n"]
                assert n in n_to_page_id
                items.append(
                    TEIBlock(
                        xml=_to_string(child),
                        slug=n,
                        page_id=n_to_page_id[n],
                    )
                )

    return TEIRewrite(items=items, errors=[], page_statuses=page_statuses)


def _write_tei_header(xf, project: db.Project, config: db.PublishConfig):
    text = config.text
    with xf.element("teiHeader"):
        with xf.element("fileDesc"):
            with xf.element("titleStmt"):
                with xf.element("title", {"type": "main"}):
                    xf.write(text.title)
                with xf.element("title", {"type": "sub"}):
                    xf.write("A machine-readable edition")
                if text.author:
                    with xf.element("author"):
                        xf.write(text.author.name)
                with xf.element("principal"):
                    xf.write("Arun Prasad")
                with xf.element("respStmt"):
                    with xf.element("persName"):
                        # TODO: For now, just me. Change this in the future.
                        xf.write("Arun Prasad")
                    with xf.element("resp"):
                        xf.write("Creation of machine-readable version.")

            with xf.element("publicationStmt"):
                with xf.element("authority"):
                    xf.write("Ambuda (https://ambuda.org)")
                with xf.element("availability"):
                    with xf.element("p"):
                        xf.write(
                            "Distributed by Ambuda under a Creative Commons CC0 1.0 Universal Licence (public domain)"
                        )
                with xf.element("date"):
                    xf.write(date.today().isoformat())

            with xf.element("notesStmt"):
                with xf.element("note"):
                    xf.write(
                        "This text has been created by direct export from Ambuda's proofing environment."
                    )

            with xf.element("sourceDesc"):
                with xf.element("bibl"):
                    if project.print_title:
                        with xf.element("title"):
                            xf.write(project.print_title)
                    if project.editor:
                        with xf.element("editor"):
                            with xf.element("name"):
                                xf.write(project.editor)
                    if project.publisher:
                        with xf.element("publisher"):
                            xf.write(project.publisher)
                    if project.publication_location:
                        with xf.element("pubPlace"):
                            xf.write(project.publication_location)
                    if project.publication_year:
                        with xf.element("date"):
                            xf.write(project.publication_year)
                    if project.author:
                        with xf.element("author"):
                            xf.write(project.author)

        with xf.element("encodingDesc"):
            with xf.element("projectDesc"):
                with xf.element("p"):
                    xf.write("Ambuda is an online library of Sanskrit literature.")
            with xf.element("editorialDesc"):
                with xf.element("normalization"):
                    with xf.element("p"):
                        xf.write(
                            "Normalization of whitespace around dandas and other punctuation marks."
                        )

        with xf.element("revisionDesc"):
            pass


def create_tei_document(
    project: db.Project,
    config: db.PublishConfig,
    out_path: Path | None = None,
    revisions: list[db.Revision] | None = None,
) -> TEIRewrite:
    """Convert the project to a TEI document for publication.

    If *out_path* is ``None``, only the conversion data is returned and no
    XML file is written.

    Approach:
    - rewrite proof XML into TEI XML. Proofing XML is more user-friendly than TEI XMl,
      and we're using it for now until we improve our editor.
    - stitch pages and blocks together, accounting for page breaks, fragments, etc.

    Notes:
    - `revisions` is exposed for dependency injection.
    """

    if revisions is None:
        session = q.get_session()
        subq = (
            select(db.Revision.page_id, func.max(db.Revision.id).label("max_id"))
            .where(db.Revision.project_id == project.id)
            .group_by(db.Revision.page_id)
            .subquery()
        )
        revisions = (
            session.execute(
                select(db.Revision)
                .join(subq, db.Revision.id == subq.c.max_id)
                .join(db.Page, db.Revision.page_id == db.Page.id)
                .order_by(db.Page.order)
            )
            .scalars()
            .all()
        )

    conversion = _rewrite_project_to_tei_xml(project, config, revisions=revisions)
    if out_path is None:
        return conversion

    errors = conversion.errors
    with etree.xmlfile(out_path, encoding="utf-8") as xf:
        xf.write_declaration()

        with xf.element("TEI", xmlns="http://www.tei-c.org/ns/1.0"):
            _write_tei_header(xf, project, config)

            with xf.element(
                "text", {"xml:id": config.text.slug, "xml:lang": config.text.language}
            ):
                with xf.element("body"):
                    items = conversion.items
                    for item in items:
                        if isinstance(item, TEISection):
                            with xf.element("div", {"n": item.slug}):
                                for block in item.blocks:
                                    el = _safe_fromstring(block.xml)
                                    el.set("n", block.slug)
                                    xf.write(el)
                        elif isinstance(item, TEIBlock):
                            el = _safe_fromstring(item.xml)
                            el.set("n", item.slug)
                            xf.write(el)
                        else:
                            raise ValueError(f"Unknown item type :{item.__name__}")
            # </text>
        # </TEI>

    # Indent for a more pleasant appearance during exports, etc..
    indent_xml_file_in_place(out_path)

    return conversion


def parse_tei_document(xml_path: Path) -> TEIDocument:
    """Parse a TEI document into its basic components.

    NOTE: this function excludes important metadata, such as the block --> page mapping.
    To preserve that data, use `create_tei_document` instead.
    """
    NS = "{http://www.tei-c.org/ns/1.0}"
    BLOCK_TAGS = {f"{NS}lg", f"{NS}p", f"{NS}head", f"{NS}trailer", f"{NS}sp"}

    header = None
    section_map = {}
    for event, elem in etree.iterparse(str(xml_path), events={"end"}):
        if elem.tag == f"{NS}teiHeader":
            header = _to_string(elem).strip()

        elif elem.tag in BLOCK_TAGS:
            n = elem.attrib.get("n")
            if not n:
                continue

            # Strip namespaces
            for x in elem.getiterator():
                x.tag = etree.QName(x).localname

            block_xml = _to_string(elem).strip()
            section_n, _, block_n = n.rpartition(".")
            section_n = section_n or SINGLE_SECTION_SLUG
            section_map.setdefault(section_n, []).append(
                TEIBlock(xml=block_xml, slug=n, page_id=0)
            )

            elem.clear()

    assert header
    sections = []
    for section_slug, blocks in section_map.items():
        section = TEISection(slug=section_slug, blocks=blocks)
    sections.append(section)

    return TEIDocument(header=header, sections=sections)
