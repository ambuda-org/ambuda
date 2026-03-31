"""Utilities for exporting texts in various formats."""

import csv
import hashlib
import io

import logging
import shutil
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from xml.etree import ElementTree as ET

from ebooklib import epub
from lxml import etree
from pydantic import BaseModel
from sqlalchemy import func as sqla_func
from sqlalchemy.orm import object_session
from ambuda.utils.vidyut_shim import transliterate, Scheme

import ambuda.database as db
from ambuda.utils.datetime import utc_datetime_timestamp
from ambuda.utils.s3 import S3Path


EXPORT_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)


class ExportType(StrEnum):
    #: TEI-conformant XML. This is our root export. That is, we use this export
    #: to create downstream exports like PLAIN_TEX and PDF
    XML = "xml"
    PLAIN_TEXT = "plain-text"
    PDF = "pdf"
    EPUB = "epub"
    TOKENS = "tokens"
    VOCAB = "vocab"


class ExportScheme(StrEnum):
    DEVANAGARI = "Devanagari"
    # KANNADA = "Kannada"
    # GRANTHA = "Grantha"

    @property
    def title(self) -> str:
        return self.value

    @property
    def slug(self) -> str:
        """The file-readable name of this scheme (for filenames, eg)."""
        return self.value.lower()

    @property
    def scheme(self) -> Scheme:
        """The transliteration settings associated with this script."""
        map = {
            ExportScheme.DEVANAGARI: Scheme.Devanagari,
            # ExportScheme.KANNADA: Scheme.Kannada,
            # ExportScheme.GRANTHA: Scheme.Grantha,
        }
        assert self.value in map
        return map[self.value]


class ExportConfig(BaseModel):
    #: A human-readable label for this export, for UIs etc.
    label: str
    #: The type of export (PDF, plain text, etc.)
    type: ExportType
    #: The filename pattern for this export. Patterns must be unique across
    #: export configs.
    slug_pattern: str
    #: The MIME type for this export.
    mime_type: str
    #: The output scheme for this export. If not set, use Devanagari.
    scheme: ExportScheme | None = None

    _S3_PREFIX = "assets/text-exports"

    def slug(self, text_slug: str) -> str:
        return self.slug_pattern.format(text_slug)

    def s3_path(self, bucket: str, text_slug: str) -> S3Path:
        return S3Path(bucket, f"{self._S3_PREFIX}/{self.slug(text_slug)}")

    @cached_property
    def suffix(self) -> str:
        return self.slug_pattern.format("")

    def matches(self, filename: str) -> bool:
        return filename.endswith(self.suffix)


class BulkExportType(StrEnum):
    """Export types specific to batch exports.

    These are basically 1:1 with regular export types, but this may change in the future, so
    for now, model them separately.
    """

    #: Bulk export of TEI XML
    XML = "xml"
    #: Bulk export of text data
    TEXT = "text"

    #: Metadata summary, including collection details.
    METADATA_JSON = "metadata-json"
    #: A list of all <teiHeader> elements from all corpus documents.
    TEI_HEADERS = "tei-headers"


class BulkExportConfig(BaseModel):
    #: A human-readable label for this export, for UIs etc.
    label: str
    #: The specific bulk export type.
    type: BulkExportType
    #: The filename pattern for this export. Patterns must be unique across
    #: export configs.
    slug_pattern: str

    _S3_PREFIX = "assets/text-exports"

    @property
    def slug(self) -> str:
        return self.slug_pattern

    def s3_path(self, bucket: str) -> S3Path:
        return S3Path(bucket, f"{self._S3_PREFIX}/{self.slug}")

    @property
    def mime_type(self) -> str:
        return "application/zip"


EXPORTS = [
    ExportConfig(
        label="XML",
        type=ExportType.XML,
        slug_pattern="{}.xml",
        mime_type="application/xml",
    ),
    ExportConfig(
        label="Plain text",
        type=ExportType.PLAIN_TEXT,
        slug_pattern="{}.txt",
        mime_type="text/csv",
    ),
    *[
        ExportConfig(
            label=f"PDF ({scheme.title})",
            type=ExportType.PDF,
            slug_pattern="{}" + f"-{scheme.slug}.pdf",
            mime_type="application/pdf",
            scheme=scheme,
        )
        for scheme in ExportScheme
    ],
    ExportConfig(
        label="EPUB",
        type=ExportType.EPUB,
        slug_pattern="{}.epub",
        mime_type="application/epub+zip",
    ),
    ExportConfig(
        label="Token data (CSV)",
        type=ExportType.TOKENS,
        slug_pattern="{}-tokens.csv",
        mime_type="text/csv",
    ),
    ExportConfig(
        label="Vocabulary list (CSV)",
        type=ExportType.VOCAB,
        slug_pattern="{}-vocab.csv",
        mime_type="text/csv",
    ),
]


BULK_EXPORTS = [
    BulkExportConfig(
        label="All TEI XML files",
        type=BulkExportType.XML,
        slug_pattern="ambuda-xml.zip",
    ),
    BulkExportConfig(
        label="All texts (plain text)",
        type=BulkExportType.TEXT,
        slug_pattern="ambuda-text.zip",
    ),
    BulkExportConfig(
        label="Library metadata (JSON)",
        type=BulkExportType.METADATA_JSON,
        slug_pattern="metadata.json",
    ),
    BulkExportConfig(
        label="TEI headers (XML)",
        type=BulkExportType.TEI_HEADERS,
        slug_pattern="tei-headers.xml",
    ),
]


def font_directory(s3_bucket: str) -> Path:
    """Get a path to our font files, loading from S3 if necessary.

    :param s3_bucket: the S3 bucket name
    """

    temp_dir = Path(tempfile.gettempdir())
    fonts_dir = temp_dir / "ambuda_fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)

    font_path = fonts_dir / "NotoSerifDevanagari.ttf"
    if font_path.exists():
        logger.info(f"Font path exists: {font_path}")
        return fonts_dir

    try:
        # TODO: variable fonts are not supported well in typst.
        path = S3Path(
            s3_bucket, "assets/fonts/NotoSerifDevanagari-VariableFont_wdth,wght.ttf"
        )
        logger.info(f"Downloading font from S3: {path.path}")
        path.download_file(font_path)
    except Exception as e:
        logger.error(f"Exception while downloading font: {e}")
    return fonts_dir


def create_xml_file(text: db.Text, out_path: Path) -> None:
    """Create a TEI XML file from the given path.

    TEI XML is our canonical file export format from which all other exports are derived.
    It contains structured text data and rich metadata.  The teiHeader is taken directly
    from the text's stored header.
    """

    with etree.xmlfile(out_path, encoding="utf-8") as xf:
        xf.write_declaration()

        with xf.element("TEI", xmlns="http://www.tei-c.org/ns/1.0"):
            if text.header:
                xf.write(etree.fromstring(text.header))
            else:
                with xf.element("teiHeader"):
                    with xf.element("fileDesc"):
                        pass

            session = object_session(text)
            assert session

            with xf.element(
                "text",
                {"xml:id": text.slug, "xml:lang": text.language or "sa"},
            ):
                with xf.element("body"):
                    safe_parser = etree.XMLParser(
                        resolve_entities=False, load_dtd=False, recover=True
                    )
                    for section in text.sections:
                        with xf.element("div", n=section.slug):
                            for block in section.blocks:
                                el = etree.fromstring(block.xml, safe_parser)
                                el.set("n", block.slug)
                                xf.write(el)
                        session.expire(section)


def create_plain_text(text: db.Text, file_path: Path, xml_path: Path) -> None:
    timestamp = utc_datetime_timestamp()

    if not xml_path.exists():
        raise FileNotFoundError(
            f"XML file not found at {xml_path}. "
            "XML must be generated before plain text export."
        )

    with open(file_path, "w") as f:
        f.write(f"# {text.title}\n")
        f.write(f"# Exported from ambuda.org on {timestamp}\n\n")

        is_first = True
        ns = "{http://www.tei-c.org/ns/1.0}"
        for event, elem in etree.iterparse(
            str(xml_path), events=("end",), recover=True
        ):
            parent = elem.getparent()
            if parent is not None and parent.tag in (f"{ns}body", f"{ns}div"):
                slug = elem.get("n")
                if not slug:
                    continue

                if not is_first:
                    f.write("\n\n")
                is_first = False

                elem_str = etree.tostring(elem, encoding="unicode")
                xml = ET.fromstring(elem_str)
                for el in xml.iter():
                    if el.tag == "l":
                        el.tail = "\n"
                    el.tag = None
                f.write(ET.tostring(xml, encoding="unicode").strip())

                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]


def create_pdf(
    text: db.Text,
    file_path: Path,
    s3_bucket: str,
    xml_path: Path,
    export_scheme: ExportScheme,
) -> None:
    """Create a PDF file from the given text."""
    import typst

    timestamp = utc_datetime_timestamp()

    if not xml_path.exists():
        raise FileNotFoundError(
            f"XML file not found at {xml_path}. "
            "XML must be generated before PDF export."
        )

    template_path = Path(__file__).parent.parent / "templates/exports/document.typ"
    with open(template_path, "r") as f:
        template = f.read()

    # Just in case
    text_title = transliterate(text.title, Scheme.HarvardKyoto, Scheme.Devanagari)
    # Now, transliterate to output scheme.
    text_title = transliterate(text_title, Scheme.Devanagari, export_scheme.scheme)

    parts = template.split("{content}")
    header = parts[0].format(title=text_title, timestamp=timestamp)
    footer = parts[1] if len(parts) > 1 else ""

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".typ", delete=False
    ) as typst_file:
        temp_typst_path = typst_file.name

        typst_file.write(header)

        ns = "{http://www.tei-c.org/ns/1.0}"
        for event, elem in etree.iterparse(
            str(xml_path), events=("end",), recover=True
        ):
            parent = elem.getparent()
            if parent is not None and parent.tag in (f"{ns}body", f"{ns}div"):
                slug = elem.get("n")
                if slug is None:
                    continue

                typst_file.write(f'#text(size: 9pt, fill: rgb("#666666"))[{slug}]\n\n')

                elem_str = etree.tostring(elem, encoding="unicode")
                xml = ET.fromstring(elem_str)
                for el in xml.iter():
                    if el.tag == f"{ns}l":
                        # In typst, create a new line with `\`.
                        # (Escaped with pretty print is `\\\n`)
                        el.tail = " \\\n" + (el.tail or "")
                    el.tag = None
                content = ET.tostring(xml, encoding="unicode").strip()

                # Escape Typst special characters
                content = content.replace("*", r"\*")
                content = transliterate(
                    content, Scheme.Devanagari, export_scheme.scheme
                )

                typst_file.write("#sa[\n")
                typst_file.write(content)
                typst_file.write("\n]\n\n")

                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

        typst_file.write(footer)

    try:
        font_paths = [font_directory(s3_bucket)]
        _, warnings = typst.compile_with_warnings(
            temp_typst_path,
            font_paths=font_paths,
            output=file_path,
        )
        for warning in warnings:
            logger.info(f"Typst warning: {warning.message}")
            logger.info(f"Typst trace: {warning.trace}")
    finally:
        if Path(temp_typst_path).exists():
            Path(temp_typst_path).unlink()


def maybe_create_tokens(text: db.Text, out_path: Path) -> None:
    session = object_session(text)
    assert session

    has_data = False
    with open(out_path, "w") as f:
        writer = csv.writer(f, delimiter=",")

        results = (
            session.query(db.BlockParse, db.TextBlock.slug)
            .join(db.TextBlock, db.BlockParse.block_id == db.TextBlock.id)
            .filter(db.BlockParse.text_id == text.id)
            .yield_per(1000)
        )

        for block_parse, block_slug in results:
            for line in block_parse.data.splitlines():
                fields = line.split("\t")
                if len(fields) != 3:
                    continue

                form, base, parse_data = fields
                parse_data = parse_data.replace(",", " ")
                writer.writerow([block_slug, form, base, parse_data])
                has_data = True

            session.expire(block_parse)

    if not has_data:
        out_path.unlink()


def create_epub(text: db.Text, out_path: Path) -> None:
    """Create an EPUB file from the given text."""

    book = epub.EpubBook()
    book.set_identifier(f"ambuda-{text.slug}")
    book.set_title(text.title)
    book.set_language(text.language or "sa")

    session = object_session(text)
    assert session

    ns = "{http://www.tei-c.org/ns/1.0}"
    safe_parser = etree.XMLParser(resolve_entities=False, load_dtd=False)
    body_parts = []
    for section in text.sections:
        for block in section.blocks:
            try:
                el = etree.fromstring(block.xml, safe_parser)
            except Exception:
                continue

            tag = el.tag.replace(ns, "")
            if tag == "lg":
                lines = [l.text or "" for l in el.findall(f".//{ns}l")]
                if not lines:
                    lines = [l.text or "" for l in el.findall(".//l")]
                body_parts.append(
                    "<div class='verse'>" + "<br/>".join(lines) + "</div>"
                )
            elif tag == "note":
                content = etree.tostring(el, encoding="unicode", method="text")
                body_parts.append(f"<p class='footnote'>{content}</p>")
            else:
                content = etree.tostring(el, encoding="unicode", method="text")
                body_parts.append(f"<p>{' '.join(content.split())}</p>")

        session.expire(section)

    chapter = epub.EpubHtml(
        title=text.title, file_name="content.xhtml", lang=text.language or "sa"
    )
    chapter.content = (
        f"<html><head><title>{text.title}</title></head>"
        f"<body>{''.join(body_parts)}</body></html>"
    )
    book.add_item(chapter)

    book.toc = [chapter]
    book.spine = ["nav", chapter]
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    buf = io.BytesIO()
    epub.write_epub(buf, book)
    out_path.write_bytes(buf.getvalue())


def create_vocab_list(text: db.Text, out_path: Path) -> None:
    session = object_session(text)
    assert session

    results = (
        session.query(
            db.Token.base,
            sqla_func.count(sqla_func.distinct(db.Token.block_id)).label("block_count"),
            sqla_func.count().label("total_count"),
        )
        .join(db.TextBlock, db.Token.block_id == db.TextBlock.id)
        .filter(db.TextBlock.text_id == text.id)
        .group_by(db.Token.base)
        .order_by(sqla_func.count().desc())
        .all()
    )

    if not results:
        return

    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["base", "block_count", "total_count"])
        for base, block_count, total_count in results:
            writer.writerow([base, block_count, total_count])


def write_cached_xml(cache_dir: str | None, text_slug: str, xml_path: Path) -> None:
    """Copy an XML export into the local file cache for fast diffing."""
    if not cache_dir:
        return
    dest = Path(cache_dir) / "published-texts" / f"{text_slug}.xml"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xml_path, dest)


def delete_cached_xml(cache_dir: str | None, text_slug: str) -> None:
    """Remove an XML file from the local file cache."""
    if not cache_dir:
        return
    path = Path(cache_dir) / "published-texts" / f"{text_slug}.xml"
    path.unlink(missing_ok=True)


def cached_xml_path(cache_dir: str | None, text_slug: str) -> Path | None:
    """Return the path to a cached XML file, or None if it doesn't exist."""
    if not cache_dir:
        return None
    path = Path(cache_dir) / "published-texts" / f"{text_slug}.xml"
    if path.exists():
        return path
    return None


def read_cached_xml(cache_dir: str | None, text_slug: str) -> str | None:
    """Read an XML file from the local file cache, or return None."""
    path = cached_xml_path(cache_dir, text_slug)
    if path:
        return path.read_text(encoding="utf-8")
    return None


def create_or_update_xml_export(
    text_id: int,
    text_slug: str,
    tei_path: Path,
    s3_bucket: str,
    session,
    q,
    cache_dir: str | None = None,
) -> None:
    """Upload a TEI XML file to S3 and create/update the TextExport record.

    The local *tei_path* is deleted after a successful upload.
    """
    tei_size = tei_path.stat().st_size
    sha256_hash = hashlib.sha256()
    with open(tei_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    tei_checksum = sha256_hash.hexdigest()

    xml_config = next(e for e in EXPORTS if e.type == ExportType.XML)
    export_slug = xml_config.slug(text_slug)
    s3_path = xml_config.s3_path(s3_bucket, text_slug)
    s3_path.upload_file(tei_path)

    write_cached_xml(cache_dir, text_slug, tei_path)

    text_export = q.text_export(export_slug)
    if text_export:
        text_export.s3_path = s3_path.path
        text_export.size = tei_size
        text_export.sha256_checksum = tei_checksum
        text_export.updated_at = datetime.now(UTC)
    else:
        text_export = db.TextExport(
            text_id=text_id,
            slug=export_slug,
            export_type="xml",
            s3_path=s3_path.path,
            size=tei_size,
            sha256_checksum=tei_checksum,
        )
        session.add(text_export)
    session.commit()

    tei_path.unlink(missing_ok=True)
