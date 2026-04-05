"""Validates the structure of an XML document."""

import dataclasses as dc
from collections.abc import Callable
from enum import StrEnum
import xml.etree.ElementTree as ET

import defusedxml.ElementTree as DET


# Keep in sync with prosemirror-editor.ts::BLOCK_TYPES
class BlockType(StrEnum):
    PARAGRAPH = "p"
    VERSE = "verse"
    FOOTNOTE = "footnote"
    HEADING = "heading"
    TRAILER = "trailer"
    TITLE = "title"
    SUBTITLE = "subtitle"
    IGNORE = "ignore"
    METADATA = "metadata"


# Keep in sync with marks-config.ts::INLINE_MARKS
class InlineType(StrEnum):
    ERROR = "error"
    FIX = "fix"
    SPEAKER = "speaker"
    STAGE = "stage"
    REF = "ref"
    FLAG = "flag"
    CHAYA = "chaya"
    PRAKRIT = "prakrit"
    BOLD = "bold"
    ITALIC = "italic"
    NOTE = "note"
    ADD = "add"
    ELLIPSIS = "ellipsis"
    DELETE = "delete"
    QUOTE = "quote"
    SYNC = "sync"
    BREAK = "break"


class TEITag(StrEnum):
    # Document
    TEI = "TEI"
    TEXT = "text"
    BODY = "body"

    # header
    TEI_HEADER = "teiHeader"
    ENCODING_DESC = "encodingDesc"
    REVISION_DESC = "revisionDesc"

    # header/fileDesc
    FILE_DESC = "fileDesc"
    TITLE_STMT = "titleStmt"
    PUBLICATION_STMT = "publicationStmt"
    NOTES_STMT = "notesStmt"
    SOURCE_DESC = "sourceDesc"

    # header/fileDesc/titleStmt
    AUTHOR = "author"
    PRINCIPAL = "principal"
    RESP_STMT = "respStmt"
    PERS_NAME = "persName"
    RESP = "resp"

    # header/fileDesc/publicationStmt
    AUTHORITY = "authority"
    AVAILABILITY = "availability"
    DATE = "date"

    # header/fileDesc/sourceDesc
    BIBL = "bibl"
    EDITOR = "editor"
    NAME = "name"
    PUBLISHER = "publisher"
    PUB_PLACE = "pubPlace"

    # header/encodingDesc
    PROJECT_DESC = "projectDesc"
    EDITORIAL_DESC = "editorialDesc"
    NORMALIZATION = "normalization"
    REFS_DECL = "refsDecl"

    # Structure
    DIV = "div"
    TITLE = "title"
    HEAD = "head"
    TRAILER = "trailer"

    # Blocks
    LG = "lg"
    L = "l"
    P = "p"

    # Drama
    SP = "sp"
    STAGE = "stage"
    SPEAKER = "speaker"

    # Errors
    CHOICE = "choice"
    SEG = "seg"
    SIC = "sic"
    CORR = "corr"
    UNCLEAR = "unclear"
    SUPPLIED = "supplied"

    # Other structuring
    QUOTE = "quote"

    # Editor annotations
    ADD = "add"
    ELLIPSIS = "ellipsis"

    # References
    REF = "ref"
    NOTE = "note"

    # Page divisions
    PB = "pb"


class ValidationType(StrEnum):
    WARNING = "warning"
    ERROR = "error"


@dc.dataclass
class ValidationResult:
    type: ValidationType
    message: str

    @staticmethod
    def error(message: str) -> "ValidationResult":
        return ValidationResult(type=ValidationType.ERROR, message=message)

    @staticmethod
    def warning(message: str) -> "ValidationResult":
        return ValidationResult(type=ValidationType.WARNING, message=message)


@dc.dataclass
class ValidationSpec:
    children: set[str] = dc.field(default_factory=set)
    attrib: set[str] = dc.field(default_factory=set)


# ancestors: tuple of ancestor elements from root to current element's parent
Assertion = Callable[[ET.Element, tuple[ET.Element, ...]], list[ValidationResult]]


@dc.dataclass
class Schema:
    specs: dict[str, ValidationSpec]
    assertions: dict[str, list[Assertion]] = dc.field(default_factory=dict)


CORE_INLINE_TYPES = set(InlineType) - {InlineType.BREAK}
PROOFING_XML_VALIDATION_SPEC = {
    "page": ValidationSpec(children=set(BlockType), attrib=set()),
    BlockType.PARAGRAPH: ValidationSpec(
        children=CORE_INLINE_TYPES | {InlineType.BREAK},
        attrib={"lang", "text", "n", "merge-next", "merge-text"},
    ),
    BlockType.VERSE: ValidationSpec(
        children=CORE_INLINE_TYPES | {InlineType.BREAK},
        attrib={"lang", "text", "n", "merge-next", "merge-text"},
    ),
    BlockType.FOOTNOTE: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text", "mark"}
    ),
    BlockType.HEADING: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text", "n"}
    ),
    BlockType.TRAILER: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text", "n"}
    ),
    BlockType.TITLE: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text", "n"}
    ),
    BlockType.SUBTITLE: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text", "n"}
    ),
    BlockType.IGNORE: ValidationSpec(
        children=CORE_INLINE_TYPES, attrib={"lang", "text"}
    ),
    BlockType.METADATA: ValidationSpec(children=set(), attrib={"text"}),
    **{
        tag: ValidationSpec(children=set(InlineType), attrib=set())
        for tag in InlineType
        if tag not in (InlineType.SYNC, InlineType.BREAK)
    },
    InlineType.SYNC: ValidationSpec(
        children=set(InlineType),
        attrib={"code"},
    ),
    InlineType.BREAK: ValidationSpec(children=set(), attrib=set()),
}

# TODO:
# - `fix` is not TEI xml
# - `flag` is not TEI xml
# - `subtitle` is not supported
# - `stage` in `seg` ??? `choice` in `seg` ?
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
INLINE_TEXT = {
    TEITag.CHOICE,
    TEITag.REF,
    TEITag.SUPPLIED,
    TEITag.QUOTE,
    TEITag.NOTE,
    TEITag.PB,
    TEITag.ADD,
    TEITag.ELLIPSIS,
    TEITag.UNCLEAR,
}
TEI_XML_VALIDATION_SPEC = {
    TEITag.TEI: ValidationSpec(
        children={TEITag.TEI_HEADER, TEITag.TEXT},
    ),
    TEITag.TEI_HEADER: ValidationSpec(
        children={TEITag.FILE_DESC, TEITag.ENCODING_DESC, TEITag.REVISION_DESC},
    ),
    # -- fileDesc --
    TEITag.FILE_DESC: ValidationSpec(
        children={
            TEITag.TITLE_STMT,
            TEITag.PUBLICATION_STMT,
            TEITag.NOTES_STMT,
            TEITag.SOURCE_DESC,
        },
    ),
    TEITag.TITLE_STMT: ValidationSpec(
        children={
            TEITag.TITLE,
            TEITag.AUTHOR,
            TEITag.PRINCIPAL,
            TEITag.RESP_STMT,
        },
    ),
    TEITag.RESP_STMT: ValidationSpec(
        children={TEITag.PERS_NAME, TEITag.RESP},
    ),
    TEITag.PERS_NAME: ValidationSpec(),
    TEITag.RESP: ValidationSpec(),
    TEITag.PUBLICATION_STMT: ValidationSpec(
        children={TEITag.AUTHORITY, TEITag.AVAILABILITY, TEITag.DATE},
    ),
    TEITag.AUTHORITY: ValidationSpec(),
    TEITag.AVAILABILITY: ValidationSpec(children={TEITag.P}),
    TEITag.DATE: ValidationSpec(),
    TEITag.NOTES_STMT: ValidationSpec(children={TEITag.NOTE}),
    TEITag.SOURCE_DESC: ValidationSpec(children={TEITag.BIBL}),
    TEITag.BIBL: ValidationSpec(
        children={
            TEITag.TITLE,
            TEITag.AUTHOR,
            TEITag.EDITOR,
            TEITag.PUBLISHER,
            TEITag.PUB_PLACE,
            TEITag.DATE,
        },
    ),
    TEITag.EDITOR: ValidationSpec(children={TEITag.NAME}),
    TEITag.NAME: ValidationSpec(),
    TEITag.PUBLISHER: ValidationSpec(),
    TEITag.PUB_PLACE: ValidationSpec(),
    TEITag.PRINCIPAL: ValidationSpec(),
    TEITag.AUTHOR: ValidationSpec(),
    # -- encodingDesc --
    TEITag.ENCODING_DESC: ValidationSpec(
        children={TEITag.PROJECT_DESC, TEITag.EDITORIAL_DESC, TEITag.REFS_DECL},
    ),
    TEITag.PROJECT_DESC: ValidationSpec(children={TEITag.P}),
    TEITag.EDITORIAL_DESC: ValidationSpec(children={TEITag.NORMALIZATION}),
    TEITag.NORMALIZATION: ValidationSpec(children={TEITag.P}),
    TEITag.REFS_DECL: ValidationSpec(),
    # -- revisionDesc --
    TEITag.REVISION_DESC: ValidationSpec(),
    TEITag.TEXT: ValidationSpec(
        children={TEITag.BODY},
        # TODO: xml:id ?
        attrib={"id", "lang"},
    ),
    TEITag.BODY: ValidationSpec(
        children={
            TEITag.DIV,
            TEITag.LG,
            TEITag.P,
            TEITag.HEAD,
            TEITag.TRAILER,
            TEITag.SP,
        },
    ),
    TEITag.DIV: ValidationSpec(
        children={TEITag.LG, TEITag.P, TEITag.HEAD, TEITag.TRAILER, TEITag.SP},
        attrib={"n"},
    ),
    TEITag.SP: ValidationSpec(
        children={TEITag.SPEAKER, TEITag.P, TEITag.LG, TEITag.STAGE, "note"},
        attrib={"n"},
    ),
    TEITag.STAGE: ValidationSpec(attrib={"rend"}),
    TEITag.SPEAKER: ValidationSpec(attrib={"rend"}),
    # XML_ID is sometimes defined in third-party texts.
    TEITag.LG: ValidationSpec(children={"l", "note", "pb"}, attrib={"n", XML_ID}),
    TEITag.L: ValidationSpec(children=INLINE_TEXT, attrib=set()),
    TEITag.P: ValidationSpec(
        children=INLINE_TEXT | {TEITag.STAGE},
        attrib={"n"},
    ),
    TEITag.CHOICE: ValidationSpec(
        children={TEITag.SEG, TEITag.CORR, TEITag.SIC}, attrib={"type", "rend"}
    ),
    TEITag.SEG: ValidationSpec(children={"choice"}, attrib={XML_LANG, "rend"}),
    TEITag.HEAD: ValidationSpec(attrib={"n"}),
    TEITag.TITLE: ValidationSpec(attrib={"n", "type"}),
    TEITag.TRAILER: ValidationSpec(attrib={"n"}),
    TEITag.REF: ValidationSpec(attrib={"target", "type"}),
    TEITag.NOTE: ValidationSpec(attrib={"type", XML_ID}),
    TEITag.SIC: ValidationSpec(),
    TEITag.CORR: ValidationSpec(),
    TEITag.PB: ValidationSpec(attrib={"n"}),
    TEITag.SUPPLIED: ValidationSpec(),
    TEITag.ADD: ValidationSpec(),
    TEITag.ELLIPSIS: ValidationSpec(),
    TEITag.UNCLEAR: ValidationSpec(),
    TEITag.QUOTE: ValidationSpec(),
}


METADATA_FIELDS = {"speaker", "div.title", "div.n"}


def validate_metadata(text: str) -> list[ValidationResult]:
    """Validate metadata block content (one key=value pair per line)."""
    results = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        if "=" not in line:
            results.append(
                ValidationResult.error(
                    f"Metadata line {i}: expected 'key=value' format, got '{line}'"
                )
            )
            continue
        key, _, _ = line.partition("=")
        key = key.strip()
        if key not in METADATA_FIELDS:
            results.append(
                ValidationResult.error(
                    f"Metadata line {i}: unknown field '{key}'"
                    f" (allowed: {', '.join(sorted(METADATA_FIELDS))})"
                )
            )
    return results


def validate_xml(xml: ET.Element, schema: Schema) -> list[ValidationResult]:
    results = []

    def _validate_element(el, ancestors=()):
        tag = el.tag
        current_path = tuple(a.tag for a in ancestors) + (tag,)

        if tag not in schema.specs:
            results.append(
                ValidationResult.error(
                    f"Unknown element '{tag}' at {'/'.join(current_path)}"
                )
            )
            return

        spec = schema.specs[tag]

        for attr in el.attrib:
            if attr not in spec.attrib:
                results.append(
                    ValidationResult.error(
                        f"Unexpected attribute '{attr}' on element '{tag}' under {'/'.join(current_path)}"
                    )
                )

        for child in el:
            if child.tag not in spec.children:
                results.append(
                    ValidationResult.error(
                        f"Unexpected child element '{child.tag}' under {'/'.join(current_path)}"
                    )
                )

        for assertion in schema.assertions.get(tag, ()):
            results.extend(assertion(el, ancestors))

        child_ancestors = ancestors + (el,)
        for child in el:
            _validate_element(child, child_ancestors)

    _validate_element(xml)
    return results


# -- Assertions --


def _assert_metadata_block(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    return validate_metadata(el.text or "")


def _assert_chaya_choice(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    """Validate a <choice type="chaya"> element."""
    if el.get("type") != "chaya":
        return []

    results = []
    children = list(el)
    seg_children = [c for c in children if c.tag == TEITag.SEG]

    if len(children) != 2 or len(seg_children) != 2:
        results.append(
            ValidationResult.error(
                "choice[type=chaya] must have exactly two <seg> children"
            )
        )
        return results

    langs = {c.get(XML_LANG) for c in seg_children}
    if langs != {"pra", "sa"}:
        results.append(
            ValidationResult.error(
                "choice[type=chaya] must have one seg[@xml:lang='pra'] "
                "and one seg[@xml:lang='sa']"
            )
        )
    return results


def _assert_sp_has_speaker(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    """Check that <sp> contains a <speaker> child."""
    if any(c.tag == TEITag.SPEAKER for c in el):
        return []
    return [ValidationResult.error("<sp> must contain a <speaker>")]


def _assert_not_empty(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    """Check that an element is not empty (has text or child elements)."""
    if len(el) > 0 or (el.text and el.text.strip()):
        return []
    return [ValidationResult.error(f"<{el.tag}> must not be empty")]


def _assert_break_empty(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    """Check that <break> has no text content or children."""
    if len(el) > 0 or (el.text and el.text.strip()):
        return [
            ValidationResult.error(
                "<break> must be a void element (no text or children)"
            )
        ]
    return []


def _assert_seg_rend(
    el: ET.Element, ancestors: tuple[ET.Element, ...]
) -> list[ValidationResult]:
    """Check that seg/@rend only appears inside choice[type=chaya]."""
    if "rend" not in el.attrib:
        return []

    for ancestor in ancestors:
        if ancestor.tag == TEITag.CHOICE and ancestor.get("type") == "chaya":
            return []

    return [
        ValidationResult.error("seg[@rend] is only valid inside choice[type=chaya]")
    ]


# -- Schemas --

PROOFING_XML_SCHEMA = Schema(
    specs=PROOFING_XML_VALIDATION_SPEC,
    assertions={
        BlockType.METADATA: [_assert_metadata_block],
        InlineType.BREAK: [_assert_break_empty],
    },
)

TEI_XML_SCHEMA = Schema(
    specs=TEI_XML_VALIDATION_SPEC,
    assertions={
        TEITag.CHOICE: [_assert_chaya_choice],
        TEITag.SEG: [_assert_seg_rend],
        TEITag.SP: [_assert_sp_has_speaker],
        TEITag.LG: [_assert_not_empty],
        TEITag.P: [_assert_not_empty],
    },
)


# -- Public API --


def validate_proofing_xml(content: str) -> list[ValidationResult]:
    try:
        root = DET.fromstring(content)
    except ET.ParseError as e:
        return [ValidationResult.error(f"XML parse error: {e}")]

    # Root tag should always be "page"
    if root.tag != "page":
        return [ValidationResult.error(f"Root tag must be 'page', got '{root.tag}'")]

    return validate_xml(root, PROOFING_XML_SCHEMA)


def validate_tei_xml(xml: ET.Element) -> list[ValidationResult]:
    return validate_xml(xml, TEI_XML_SCHEMA)
