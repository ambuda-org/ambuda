"""Utilities for validating that a published text is well-formed."""

import logging
import os
import re
import tempfile
from pathlib import Path
from enum import StrEnum
from typing import BinaryIO, NamedTuple, Union

from lxml import etree
from pydantic import BaseModel, Field
from sqlalchemy.orm import object_session
from ambuda.utils.vidyut_shim import transliterate, Scheme

import ambuda.database as db
from ambuda.utils.xml_validation import XML_ID, validate_tei_xml
from ambuda.utils.text_exports import cached_xml_path, create_xml_file

_log = logging.getLogger(__name__)


# TEI namespace.
NS = "{http://www.tei-c.org/ns/1.0}"
BLOCK_TAGS = {f"{NS}lg", f"{NS}p", f"{NS}head", f"{NS}trailer", f"{NS}sp"}
TEI_HEADER = f"{NS}teiHeader"
TEI_TEXT = f"{NS}text"
TEI_DIV = f"{NS}div"

# Regex to split out xmlns from serialized XML.
# I tried configuring lxml to not output this string but didn't succeed, hence the regex.
_RE_XMLNS = re.compile(r'\s*xmlns(?::\w+)?="[^"]*"')


class Token(NamedTuple):
    """A single parsed token (word form + linguistic base)."""

    form: str
    base: str


# Mapping of block_id -> list of tokens.
# A key with an empty list means the block is "parsed" but has no data.
TokenData = dict[int, list[Token]]


def _load_token_stems(text_id: int, session, block_ids: set[int]) -> TokenData | None:
    """Load token data for a text.

    Avoid the ORM to avoid massive overhead in creating ~millions of tiny ORM objects.
    """
    if not session:
        return None

    if not block_ids:
        return {}

    tokens = (
        session.query(db.Token.block_id, db.Token.form, db.Token.base)
        .join(db.TextBlock, db.Token.block_id == db.TextBlock.id)
        .filter(db.TextBlock.text_id == text_id)
        .all()
    )
    if tokens:
        result: TokenData = {}
        for block_id, form, base in tokens:
            result.setdefault(block_id, []).append(Token(form, base))
        return result

    # Fall back to deprecated BlockParse — column-only query.
    block_parses = (
        session.query(db.BlockParse.block_id, db.BlockParse.data)
        .filter(db.BlockParse.text_id == text_id)
        .all()
    )

    result = {}
    for block_id, data in block_parses:
        pairs: list[Token] = []
        for line in data.splitlines():
            fields = line.split()
            if len(fields) > 1:
                pairs.append(Token(fields[0], fields[1]))
        result[block_id] = pairs
    return result


def _strip_ns_inplace(elem: etree._Element) -> None:
    """Remove namespace prefixes from tags in-place (element and descendants)."""
    for el in elem.iter():
        el.tag = etree.QName(el).localname


def _to_string(xml: etree._Element) -> str:
    """Serialize an element, stripping all namespace declarations."""
    etree.indent(xml, space="  ")
    _strip_ns_inplace(xml)
    return _RE_XMLNS.sub("", etree.tostring(xml, encoding="unicode"))


class ValidationGroupName(StrEnum):
    #: XML structure
    XML = "XML"
    #: Text content
    TEXT = "Text"
    #: Metrical properties
    METER = "Meter"
    #: Segmented tokens
    TOKENS = "Tokens"


class XMLError(BaseModel):
    type: str = "xml"
    #: The XML associated with this error (truncated to the first 1000 chars)
    xml: str = ""
    #: The messages associated with this error.
    messages: list[str]


class TokenError(BaseModel):
    type: str = "token"
    #: The messages associated with this error.
    messages: list[str]


class ChandasError(BaseModel):
    #: The type associated with this error (always "chandas")
    type: str = "chandas"
    n: str | None
    #: The XML associated with this error (truncated to the first 1000 chars)
    xml: str
    #: Scanned aksharas.
    scan: list[list[dict]]


class ValidationResult(BaseModel):
    #: The type of validation
    group: str = ""
    #: Human-readable label for this test.
    description: str = ""
    num_ok: int = 0
    num_total: int = 0
    errors: list[dict] = Field(default_factory=list)

    def incr_ok(self):
        self.num_ok += 1

    def incr_total(self):
        self.num_total += 1

    def add_structured_error(self, struct: dict):
        # Show a reasonable number of errors, but not so many that it's overwhelming or causes
        # crashes for large texts.
        if len(self.errors) > 100:
            return
        self.errors.append(struct)


class ValidationGroup(BaseModel):
    """A named group of validation results."""

    name: str
    results: list[ValidationResult] = Field(default_factory=list)


class ReportSummary(BaseModel):
    """Lightweight summary of a validation report."""

    num_passed: int = 0
    num_total: int = 0


class ValidationReport(BaseModel):
    """The full validation report for some text."""

    groups: list[ValidationGroup] = Field(default_factory=list)
    summary: ReportSummary = Field(default_factory=ReportSummary)

    def compute_summary(self) -> "ValidationReport":
        """Recompute the summary from the current groups. Returns self for chaining."""
        passed = 0
        total = 0
        for group in self.groups:
            for result in group.results:
                if result.num_total > 0:
                    total += 1
                    if result.num_ok == result.num_total:
                        passed += 1
        self.summary = ReportSummary(num_passed=passed, num_total=total)
        return self


class XMLValidationRule:
    """Base class for validators that operate on XML elements."""

    #: The group this rule belongs to.
    group: ValidationGroupName
    #: Human-readable label for this test.
    description: str

    def __init__(self):
        self.ret = ValidationResult()

    def process(self, xml: etree._Element) -> None:
        """Process a single XML element (block, header, div, etc.)."""
        raise NotImplementedError

    def result(self) -> ValidationResult:
        self.ret.group = self.group
        self.ret.description = self.description
        return self.ret

    @classmethod
    def validate_doc(cls, doc: etree._Element) -> ValidationResult:
        """Run this rule over every block in a parsed XML document."""
        inst = cls()
        for div in doc.findall("./div"):
            for block in div:
                inst.process(block)
        return inst.result()


class TokenValidationRule:
    """Base class for validators that operate on token data."""

    #: The group this rule belongs to.
    group: ValidationGroupName
    #: Human-readable label for this test.
    description: str

    def __init__(self):
        self.ret = ValidationResult()

    def process(self, block_ids: set[int], token_data: TokenData | None) -> None:
        """Validate token data against block IDs."""
        raise NotImplementedError

    def result(self) -> ValidationResult:
        self.ret.group = self.group
        self.ret.description = self.description
        return self.ret


class UniqueBlockIds(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "All blocks have unique identifiers"

    def __init__(self):
        super().__init__()
        self.seen: set[str] = set()

    def process(self, xml: etree._Element) -> None:
        n = xml.attrib.get("n")
        if n:
            self.ret.incr_total()
            if n in self.seen:
                block_xml = _to_string(xml)[:1000]
                self.ret.add_structured_error(
                    XMLError(
                        messages=[f"Duplicate `n` value: {n}"], xml=block_xml
                    ).model_dump()
                )
            else:
                self.seen.add(n)
                self.ret.incr_ok()


class WellFormedXml(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "XML conforms to the TEI schema"

    def process(self, xml: etree._Element) -> None:
        self.ret.incr_total()
        results = validate_tei_xml(xml)
        if results:
            xml_str = _to_string(xml)[:1000]
            self.ret.add_structured_error(
                XMLError(
                    messages=[r.message for r in results], xml=xml_str
                ).model_dump()
            )
        else:
            self.ret.incr_ok()


class ValidTextId(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "<text> @xml:id matches text's slug"

    def __init__(self, slug: str):
        super().__init__()
        self.slug = slug

    def process(self, xml: etree._Element) -> None:
        self.ret.incr_total()
        xml_id = xml.get(XML_ID)
        if xml_id == self.slug:
            self.ret.incr_ok()
        else:
            self.ret.add_structured_error(
                XMLError(
                    messages=[f"Expected xml:id='{self.slug}', got '{xml_id}'"]
                ).model_dump()
            )


class UniqueDivIds(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "All <div> elements set 'n' with unique values"

    def __init__(self):
        super().__init__()
        self.seen: set[str] = set()

    def process(self, xml: etree._Element) -> None:
        self.ret.incr_total()
        n = xml.get("n")
        if n is None:
            self.ret.add_structured_error(
                XMLError(messages=["<div> is missing 'n' attribute"]).model_dump()
            )
        elif n in self.seen:
            self.ret.add_structured_error(
                XMLError(messages=[f"Duplicate <div> n value: '{n}'"]).model_dump()
            )
        else:
            self.seen.add(n)
            self.ret.incr_ok()


class HeadTrailerSlugs(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "Singleton <head> and <trailer> slugs end with .head / .trailer"

    def __init__(self):
        super().__init__()
        # Per-parent captures: id(parent) -> {tag -> [(n, xml_str), ...]}
        # We accumulate per block and apply the singleton check in result(),
        # because iterparse clears each block before its parent's end event fires.
        self._captures: dict[int, dict[str, list[tuple[str, str]]]] = {}

    def process(self, xml: etree._Element) -> None:
        if xml.tag not in ("head", "trailer"):
            return
        parent = xml.getparent()
        if parent is None:
            return
        n = xml.get("n", "")
        xml_str = _to_string(xml)[:1000]
        by_tag = self._captures.setdefault(id(parent), {})
        by_tag.setdefault(xml.tag, []).append((n, xml_str))

    def result(self) -> ValidationResult:
        for by_tag in self._captures.values():
            for child_tag, suffix in (("head", ".head"), ("trailer", ".trailer")):
                entries = by_tag.get(child_tag, [])
                if len(entries) != 1:
                    continue
                n, xml_str = entries[0]
                self.ret.incr_total()
                if n == child_tag or n.endswith(suffix):
                    self.ret.incr_ok()
                else:
                    self.ret.add_structured_error(
                        XMLError(
                            messages=[
                                f"<{child_tag}> slug '{n}' must be '{child_tag}' or end with '{suffix}'"
                            ],
                            xml=xml_str,
                        ).model_dump()
                    )
        return super().result()


class VerseSlugsOmitLg(XMLValidationRule):
    group = ValidationGroupName.XML
    description = "Verse-only texts: <lg> slugs do not contain 'lg'"

    def __init__(self):
        super().__init__()
        self.slugs: dict[str, list[str]] = {}

    def process(self, xml: etree._Element) -> None:
        tag = xml.tag
        n = xml.get("n")
        if tag in ("lg", "p") and n:
            self.slugs.setdefault(tag, []).append(n)

    def result(self) -> ValidationResult:
        lg_slugs = self.slugs.get("lg", [])
        has_p = "p" in self.slugs
        if lg_slugs and not has_p:
            for n in lg_slugs:
                self.ret.incr_total()
                if "lg" in n:
                    self.ret.add_structured_error(
                        XMLError(
                            messages=[f"<lg> slug '{n}' should not contain 'lg'"],
                        ).model_dump()
                    )
                else:
                    self.ret.incr_ok()
        return super().result()


class WellFormedText(XMLValidationRule):
    group = ValidationGroupName.TEXT
    description = "Devanagari text is well-formed"

    # Sanskrit text in Devanagari is expected to match this regex.
    #
    # Unicode tables:
    # - https://www.unicode.org/charts/PDF/U0900.pdf
    # - https://www.unicode.org/charts/PDF/UA8E0.pdf
    RE_ILLEGAL = r"([^\u0900-\u097F\ua8e0-\ua8ff\s!,\-\.\(\)\?])"

    # Sequences that are valid Unicode but impossible in Sanskrit (common OCR artifacts).
    FORBIDDEN_SEQUENCES = ["क्लृ"]

    def _check_text(self, text: str, elem: etree._Element) -> str | None:
        """Check a text string for issues. Returns an error message or None."""
        if m := re.search(self.RE_ILLEGAL, text):
            return f"Unexpected character '{m.group(1)}' in text <{text}>"
        for seq in self.FORBIDDEN_SEQUENCES:
            if seq in text:
                return f"Forbidden sequence '{seq}' in text <{text}>"
        return None

    def process(self, xml: etree._Element) -> None:
        for elem in xml.iter():
            self.ret.incr_total()
            error = self._check_text(elem.text or "", elem) or self._check_text(
                elem.tail or "", elem
            )
            if error:
                block_xml = _to_string(elem)[:1000]
                self.ret.add_structured_error(
                    XMLError(messages=[error], xml=block_xml).model_dump()
                )
            else:
                self.ret.incr_ok()


class NoLeadingTrailingSpaces(XMLValidationRule):
    group = ValidationGroupName.TEXT
    description = "No leading or trailing spaces in text elements"

    def process(self, xml: etree._Element) -> None:
        allowed_tags = {"l", "p", "speaker", "stage"}
        for elem in xml.iter():
            if elem.tag not in allowed_tags:
                continue
            self.ret.incr_total()
            text = "".join(elem.itertext())
            if text != text.strip():
                elem_xml = _to_string(elem)[:1000]
                self.ret.add_structured_error(
                    XMLError(
                        messages=[f"<{elem.tag}> has leading/trailing whitespace"],
                        xml=elem_xml,
                    ).model_dump()
                )
            else:
                self.ret.incr_ok()


class VerseNumberMatch(XMLValidationRule):
    group = ValidationGroupName.TEXT
    description = "Verse numbers match `n` attribute"

    # Captures verse numbers of the form ॥१-३॥ ॥१.३॥ ॥१-३-३॥ ॥१॥ etc.
    RE_VERSE_NUMBERS = r"॥\s*([\u0966-\u096F]+(?:[-\.]+[\u0966-\u096F]+)*)\s*॥$"

    def process(self, xml: etree._Element) -> None:
        if xml.tag != "lg":
            return
        if expected_n := xml.attrib.get("n", None):
            _, _, expected_n = expected_n.rpartition(".")
            text = "".join(xml.itertext())
            if m := re.search(self.RE_VERSE_NUMBERS, text):
                self.ret.incr_total()
                m_n = re.split(r"[-\.]", m.group(1))[-1]
                actual_n = transliterate(m_n, Scheme.Devanagari, Scheme.Slp1)
                if expected_n != actual_n:
                    block_xml = _to_string(xml)[:1000]
                    self.ret.add_structured_error(
                        XMLError(
                            messages=[
                                f"Verse number mismatch. (expected '{expected_n}', saw '{actual_n}')"
                            ],
                            xml=block_xml,
                        ).model_dump()
                    )
                else:
                    self.ret.incr_ok()


def _get_chandas():
    from ambuda.utils.vidyut_loaders import get_chandas

    return get_chandas()


def _get_kosha():
    from ambuda.utils.vidyut_loaders import get_kosha

    data_dir = os.environ.get("VIDYUT_DATA_DIR", "data/vidyut-0.4.0")
    return get_kosha(data_dir)


class MeterCheck(XMLValidationRule):
    group = ValidationGroupName.METER
    description = "All verses have a known meter"

    # The Chandas Rust library panics on very long inputs (index out of bounds
    # in sounds.rs).  Cap the input length to avoid crashing the process.
    _MAX_CLASSIFY_LEN = 1500

    _CHANDAS_WHITELIST = ["उवाच"]

    def __init__(self):
        super().__init__()
        self.chandas = _get_chandas()

    @staticmethod
    def _extract_element_text(elem: etree._Element) -> str:
        """Extract text from an element, skipping <ref> and <sic> content.

        For <choice> elements, only the <corr> child's text is used.
        For <subst> elements, only the <add> child's text is used."""
        parts = [elem.text or ""]
        for child in elem:
            if child.tag == "ref" or child.tag == "sic":
                pass
            elif child.tag == "choice":
                corr = child.find("corr")
                if corr is not None:
                    parts.append(corr.text or "")
            elif child.tag == "subst":
                add = child.find("add")
                if add is not None:
                    parts.append(add.text or "")
            else:
                parts.append(MeterCheck._extract_element_text(child))
            parts.append(child.tail or "")
        return "".join(parts)

    @staticmethod
    def _extract_verse_text(block: etree._Element) -> str:
        """Extract text from an <lg> block, one line per <l>."""
        return "\n".join(
            MeterCheck._extract_element_text(l_elem) for l_elem in block.findall("l")
        )

    @staticmethod
    def _is_shloka(aksharas: list) -> bool:
        """Check if aksharas match the shloka pattern: 1-3 lines of 16 syllables
        each, with positions 13-15 (1-indexed) having the pattern L, G, L."""
        if not (1 <= len(aksharas) <= 3):
            return False
        for line in aksharas:
            if len(line) != 16:
                return False
            if (
                line[12].weight != "L"
                or line[13].weight != "G"
                or line[14].weight != "L"
            ):
                return False
        return True

    @staticmethod
    def _is_tristubh(aksharas: list) -> bool:
        """Check if aksharas match the trishtubh pattern: 2 or 4 lines of 11
        syllables each, with positions 2-10 (1-indexed) matching G L G G L L G L G."""
        if len(aksharas) not in (2, 4):
            return False
        expected = ["G", "L", "G", "G", "L", "L", "G", "L", "G"]
        for line in aksharas:
            if len(line) != 11:
                return False
            if [line[i].weight for i in range(1, 10)] != expected:
                return False
        return True

    def _mark_odd_aksharas(self, scan: list[list[dict]]) -> None:
        """Mark syllables that deviate from the expected pattern.

        Policy: if any individual lines have a detectable meter, treat them as
        golden and highlight deviations in the remaining lines.  Otherwise fall
        back to majority vote per column."""
        if not scan:
            return

        # Try to detect golden lines by classifying each line individually.
        golden_indices: list[int] = []
        for i, line in enumerate(scan):
            slp1 = "".join(s["text"] for s in line)
            slp1 = transliterate(slp1, Scheme.Devanagari, Scheme.Slp1)
            m = self.chandas.classify(slp1)
            if m.padya:
                golden_indices.append(i)

        max_len = max(len(line) for line in scan)

        if golden_indices:
            # Build expected weight per position from golden lines (first golden wins).
            expected: list[str | None] = [None] * max_len
            for gi in golden_indices:
                for j, syl in enumerate(scan[gi]):
                    if expected[j] is None:
                        expected[j] = syl["weight"]
            for i, line in enumerate(scan):
                if i in golden_indices:
                    for syl in line:
                        syl["odd"] = False
                else:
                    for j, syl in enumerate(line):
                        syl["odd"] = (
                            expected[j] is not None and syl["weight"] != expected[j]
                        )
        else:
            # Majority vote per column.
            for j in range(max_len):
                weights = [line[j]["weight"] for line in scan if j < len(line)]
                if not weights:
                    continue
                majority = max(set(weights), key=weights.count)
                for line in scan:
                    if j < len(line):
                        line[j]["odd"] = line[j]["weight"] != majority

    def process(self, block: etree._Element) -> None:
        if block.tag != "lg":
            return
        self.ret.incr_total()
        clean_text = self._extract_verse_text(block).strip()
        if any(w in clean_text.split() for w in self._CHANDAS_WHITELIST):
            self.ret.incr_ok()
            return
        slp1 = transliterate(clean_text, Scheme.Devanagari, Scheme.Slp1)

        if len(slp1) > self._MAX_CLASSIFY_LEN:
            block_xml = _to_string(block)[:1000]
            self.ret.add_structured_error(
                XMLError(
                    messages=[f"Verse too long for meter check ({len(slp1)} chars)"],
                    xml=block_xml,
                ).model_dump()
            )
            return

        try:
            match = self.chandas.classify(slp1)
        except BaseException as exc:
            _log.warning("Chandas error on block n=%s: %s", block.attrib.get("n"), exc)
            block_xml = _to_string(block)[:1000]
            self.ret.add_structured_error(
                XMLError(
                    messages=[f"Meter check failed: {exc}"],
                    xml=block_xml,
                ).model_dump()
            )
            return

        if match.padya:
            self.ret.incr_ok()
        elif self._is_shloka(match.aksharas) or self._is_tristubh(match.aksharas):
            self.ret.incr_ok()
        else:
            block_xml = _to_string(block)
            scan = [
                [
                    {
                        "text": transliterate(a.text, Scheme.Slp1, Scheme.Devanagari),
                        "weight": a.weight,
                    }
                    for a in line_aksharas
                ]
                for line_aksharas in match.aksharas
            ]
            self._mark_odd_aksharas(scan)
            self.ret.add_structured_error(
                ChandasError(
                    n=block.attrib.get("n"),
                    xml=block_xml,
                    scan=scan,
                ).model_dump()
            )


class BlocksHaveTokenData(TokenValidationRule):
    group = ValidationGroupName.TOKENS
    description = "All blocks have token data"

    def process(self, block_ids: set[int], token_data: TokenData | None) -> None:
        if token_data is None:
            return

        for block_id in block_ids:
            self.ret.incr_total()
            if block_id in token_data:
                self.ret.incr_ok()
            else:
                self.ret.add_structured_error(
                    TokenError(
                        messages=[f"Block {block_id} has no token data"]
                    ).model_dump()
                )


class TokenStemsInDictionary(TokenValidationRule):
    group = ValidationGroupName.TOKENS
    description = "All token stems are in the lexicon"

    def __init__(self, kosha):
        super().__init__()
        self.kosha = kosha

    def process(self, block_ids: set[int], token_data: TokenData | None) -> None:
        if token_data is None:
            return

        all_stems: set[str] = set()
        for tokens in token_data.values():
            for token in tokens:
                all_stems.add(token.base)

        if not all_stems:
            return

        # Check each unique stem once.
        missing: list[str] = []
        for stem in all_stems:
            self.ret.incr_total()
            if self.kosha.get(stem):
                self.ret.incr_ok()
            else:
                missing.append(stem)

        for stem in sorted(missing):
            self.ret.add_structured_error(
                TokenError(messages=[f"Stem not in dictionary: {stem}"]).model_dump()
            )


class TokenPadasInDictionary(TokenValidationRule):
    group = ValidationGroupName.TOKENS
    description = "All token padas are in the lexicon"

    def __init__(self, kosha):
        super().__init__()
        self.kosha = kosha

    def process(self, block_ids: set[int], token_data: TokenData | None) -> None:
        if token_data is None:
            return

        all_padas: set[str] = set()
        for tokens in token_data.values():
            for token in tokens:
                all_padas.add(token.form)

        if not all_padas:
            return

        missing: list[str] = []
        for pada in all_padas:
            self.ret.incr_total()

            # HACKS for vidyut-kosha and DCS data
            clean_pada = pada
            if clean_pada.startswith("'"):
                clean_pada = "a" + clean_pada[1:]
            elif clean_pada.endswith("y"):
                clean_pada = clean_pada[:-1] + "i"
            elif clean_pada.endswith("v"):
                clean_pada = clean_pada[:-1] + "u"
            elif clean_pada.endswith("d"):
                clean_pada = clean_pada[:-1] + "t"
            elif clean_pada.endswith("n"):
                clean_pada = clean_pada[:-1] + "t"

            candidates = [clean_pada]
            if clean_pada.endswith("H"):
                candidates.append(clean_pada[:-1] + "s")
                candidates.append(clean_pada[:-1] + "r")
            elif clean_pada.endswith("o"):
                candidates.append(clean_pada[:-1] + "as")

            if any(self.kosha.get(x) for x in candidates):
                self.ret.incr_ok()
            else:
                missing.append(clean_pada)

        for pada in sorted(missing):
            self.ret.add_structured_error(
                TokenError(messages=[f"Pada not in dictionary: {pada}"]).model_dump()
            )


def _group_results(results: list[ValidationResult]) -> ValidationReport:
    """Group a flat list of ValidationResults into ValidationGroups by name."""
    groups: dict[str, ValidationGroup] = {}
    order: list[str] = []
    for r in results:
        if r.group not in groups:
            groups[r.group] = ValidationGroup(name=r.group)
            order.append(r.group)
        groups[r.group].results.append(r)
    return ValidationReport(groups=[groups[name] for name in order])


def _validate_xml_bytes(source: Union[str, BinaryIO], slug: str) -> ValidationReport:
    """Run all rules over a TEI XML source (file path or file-like object)."""
    text_id_validator = ValidTextId(slug)
    div_n_validator = UniqueDivIds()
    xml_schema_validator = WellFormedXml()
    block_validator_classes = (
        UniqueBlockIds,
        HeadTrailerSlugs,
        VerseSlugsOmitLg,
        WellFormedText,
        NoLeadingTrailingSpaces,
        VerseNumberMatch,
        MeterCheck,
    )
    block_validators = [x() for x in block_validator_classes]

    # use stream parsing for large texts like the mahabharata
    for _event, el in etree.iterparse(source, events=("end",), recover=True):
        if el.tag == TEI_HEADER:
            _strip_ns_inplace(el)
            xml_schema_validator.process(el)
            el.clear()

        elif el.tag == TEI_TEXT:
            text_id_validator.process(el)
            # Don't clear -- block children still need to be processed.

        elif el.tag == TEI_DIV:
            div_n_validator.process(el)
            # Don't clear -- block children still need to be processed.

        elif el.tag in BLOCK_TAGS:
            # Skip blocks inside <teiHeader>
            ancestor = el.getparent()
            in_header = False
            while ancestor is not None:
                if ancestor.tag == TEI_HEADER:
                    in_header = True
                    break
                ancestor = ancestor.getparent()
            if in_header:
                continue

            # Strip namespaces in-place (elem is cleared below anyway).
            _strip_ns_inplace(el)
            xml_schema_validator.process(el)
            for proc in block_validators:
                proc.process(el)

            # Clear elements as we go to avoid bloating memory
            el.clear()

            while el.getprevious() is not None:
                del el.getparent()[0]

    all_results = [
        xml_schema_validator.result(),
        text_id_validator.result(),
        div_n_validator.result(),
    ] + [p.result() for p in block_validators]
    return _group_results(all_results)


def _validate_xml(text: db.Text) -> ValidationReport:
    cache_dir = os.environ.get("SERVER_FILE_CACHE")
    cached = cached_xml_path(cache_dir, text.slug)
    if cached:
        report = _validate_xml_bytes(str(cached), text.slug)
    else:
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        create_xml_file(text, tmp_path)
        try:
            report = _validate_xml_bytes(str(tmp_path), text.slug)
        finally:
            tmp_path.unlink(missing_ok=True)

    return report


def _validate_tokens(text: db.Text) -> ValidationReport:
    """Run validations against a text's tokens."""

    session = object_session(text)
    if not session:
        return ValidationReport()

    kosha = _get_kosha()
    token_coverage = BlocksHaveTokenData()
    stem_check = TokenStemsInDictionary(kosha)
    pada_check = TokenPadasInDictionary(kosha)

    # Collect all block IDs with a lightweight column query (avoids loading
    # full TextBlock ORM objects just for the id).
    block_id_rows = (
        session.query(db.TextBlock.id).filter(db.TextBlock.text_id == text.id).all()
    )
    all_block_ids = {row[0] for row in block_id_rows}

    token_data = _load_token_stems(text.id, session, all_block_ids)

    token_validators = [token_coverage, stem_check, pada_check]
    for v in token_validators:
        v.process(all_block_ids, token_data)

    return _group_results([v.result() for v in token_validators])


def validate_text(text: db.Text) -> ValidationReport:
    """Validate a text, streaming through its TEI XML.

    Uses the cached XML at SERVER_FILE_CACHE/published-texts/{slug}.xml when
    available. Otherwise generates a temporary TEI XML from the database.
    """
    xml_report = _validate_xml(text)
    # Disable for now because the kosha is too heavy.
    # token_report = _validate_tokens(text)
    return xml_report.compute_summary()


def try_parse_text_report(payload) -> ValidationReport | None:
    """Parse a report payload. Return None on failure."""
    try:
        return ValidationReport.model_validate(payload)
    except Exception:
        return None
