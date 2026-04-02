import dataclasses as dc
import json
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel

from ambuda.utils.vidyut_shim import transliterate, Scheme
from ambuda.utils import xml

import ambuda.database as db
from ambuda import queries as q


def text_metadata(text: db.Text) -> dict:
    """Return a metadata dict for a single text."""
    return {
        "slug": text.slug,
        "title": text.title,
        "alternate_titles": [a.title for a in text.alternate_titles]
        if text.alternate_titles
        else [],
        "header": text.header,
        "config": json.loads(text.config) if text.config else None,
        "genre": text.genre.name if text.genre else None,
        "language": text.language,
        "status": text.status,
        "collections": [c.slug for c in text.collections],
    }


# -- Structured metadata models (used by public API and bulk archive) --


class AuthorMetadataEntry(BaseModel):
    slug: str
    name: str


class SourceMetadataEntry(BaseModel):
    title: str | None = None
    author: str | None = None
    editor: str | None = None
    publisher: str | None = None
    publisher_place: str | None = None
    publication_year: str | None = None


class TextUrlsEntry(BaseModel):
    xml: str | None = None
    text: str | None = None


class TextMetadataEntry(BaseModel):
    slug: str
    title: str
    alternate_titles: list[str] = []
    created_at: str | None = None
    updated_at: str | None = None
    language: str | None = None
    status: str | None = None
    parent_slug: str | None = None
    author: AuthorMetadataEntry | None = None
    source: SourceMetadataEntry | None = None
    license: str | None = None
    collections: list[str] = []
    urls: TextUrlsEntry | None = None


class CollectionMetadataEntry(BaseModel):
    slug: str
    title: str
    parent_slug: str | None = None


class LibraryMetadata(BaseModel):
    api_version: str = "1"
    created_at: str
    collections: list[CollectionMetadataEntry]
    texts: list[TextMetadataEntry]


def _isoformat_utc(dt) -> str | None:
    """Format a datetime as ISO 8601 with UTC timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def _strip_or_none(value: str | None) -> str | None:
    """Strip whitespace and return None if empty."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_source(header_xml: str | None) -> SourceMetadataEntry | None:
    """Parse TEI header XML into a SourceMetadataEntry, or None."""
    if not header_xml:
        return None
    try:
        h = xml.parse_tei_header(header_xml)
        title = _strip_or_none(h.tei_title)
        source = SourceMetadataEntry(
            title=title if title and title != "Unknown" else None,
            author=_strip_or_none(h.source_author),
            editor=_strip_or_none(h.source_editor),
            publisher=_strip_or_none(h.source_publisher),
            publisher_place=_strip_or_none(h.source_publisher_place),
            publication_year=_strip_or_none(h.source_publication_year),
        )
        return source if source.model_dump(exclude_none=True) else None
    except Exception:
        return None


def text_to_metadata(
    t: db.Text, urls: TextUrlsEntry | None = None
) -> TextMetadataEntry:
    """Convert a Text model to a metadata entry.

    :param urls: optional download URLs (requires Flask app context to build).
    """
    author = (
        AuthorMetadataEntry(slug=t.author.slug, name=t.author.name)
        if t.author
        else None
    )
    return TextMetadataEntry(
        slug=t.slug,
        title=t.title,
        alternate_titles=[a.title for a in t.alternate_titles]
        if t.alternate_titles
        else [],
        created_at=_isoformat_utc(t.created_at),
        updated_at=_isoformat_utc(t.updated_at),
        language=t.language,
        status=t.status,
        parent_slug=t.parent.slug if t.parent else None,
        author=author,
        source=_parse_source(t.header),
        license=t.license,
        collections=[c.slug for c in t.collections],
        urls=urls,
    )


def build_library_metadata(
    texts: list[db.Text],
    collections: list[db.TextCollection],
    urls_fn=None,
) -> LibraryMetadata:
    """Build a LibraryMetadata object for the given texts and collections.

    :param urls_fn: optional callable (Text -> TextUrlsEntry | None) for download URLs.
    """
    coll_id_to_slug = {c.id: c.slug for c in collections}
    return LibraryMetadata(
        created_at=datetime.now(UTC).isoformat(),
        collections=[
            CollectionMetadataEntry(
                slug=c.slug,
                title=c.title,
                parent_slug=coll_id_to_slug.get(c.parent_id) if c.parent_id else None,
            )
            for c in collections
        ],
        texts=[
            text_to_metadata(t, urls=urls_fn(t) if urls_fn else None) for t in texts
        ],
    )


def build_tei_headers_xml(texts: list[db.Text]) -> bytes:
    """Build a TEI corpus XML document containing all text headers.

    Returns UTF-8 encoded XML bytes.
    """
    from lxml import etree

    TEI_NS = "http://www.tei-c.org/ns/1.0"
    XML_NS = "http://www.w3.org/XML/1998/namespace"
    NSMAP = {None: TEI_NS}

    corpus = etree.Element("teiCorpus", nsmap=NSMAP)

    corpus_header = etree.SubElement(corpus, "teiHeader")
    file_desc = etree.SubElement(corpus_header, "fileDesc")
    title_stmt = etree.SubElement(file_desc, "titleStmt")
    title_el = etree.SubElement(title_stmt, "title")
    title_el.text = "Ambuda Library \u2014 TEI Headers"
    pub_stmt = etree.SubElement(file_desc, "publicationStmt")
    authority = etree.SubElement(pub_stmt, "authority")
    authority.text = "Ambuda (https://ambuda.org)"
    date_el = etree.SubElement(pub_stmt, "date")
    date_el.text = datetime.now(UTC).strftime("%Y-%m-%d")
    source_desc = etree.SubElement(file_desc, "sourceDesc")
    p = etree.SubElement(source_desc, "p")
    p.text = "Automatically generated from the Ambuda library."

    for t in texts:
        if not t.header:
            continue
        try:
            header_el = etree.fromstring(t.header)
        except etree.XMLSyntaxError:
            continue

        tei = etree.SubElement(corpus, "TEI")
        tei.set(f"{{{XML_NS}}}id", t.slug)

        if header_el.tag == "teiHeader" or header_el.tag == f"{{{TEI_NS}}}teiHeader":
            header_el.tag = f"{{{TEI_NS}}}teiHeader"
        tei.append(header_el)

    return etree.tostring(
        corpus,
        pretty_print=True,
        xml_declaration=True,
        encoding="UTF-8",
    )


@dc.dataclass
class TextEntry:
    text: db.Text
    children: list["TextEntry"]

    author: db.Author | None


def create_text_entries() -> list[TextEntry]:
    texts = q.texts()
    mula_texts = []
    child_texts = []
    for text in texts:
        is_mula = text.parent_id is None
        (child_texts, mula_texts)[is_mula].append(text)

    sorted_mula_texts = sorted(
        mula_texts,
        key=lambda x: transliterate(x.title, Scheme.HarvardKyoto, Scheme.Devanagari),
    )
    sorted_child_texts = sorted(
        child_texts,
        key=lambda x: transliterate(x.title, Scheme.HarvardKyoto, Scheme.Devanagari),
    )
    author_map = {x.id: x for x in q.authors()}

    text_entries = []
    text_entry_map = {}
    for text in sorted_mula_texts:
        assert text.parent_id is None

        author = author_map.get(text.author_id)
        entry = TextEntry(
            text=text,
            children=[],
            author=author,
        )
        text_entries.append(entry)
        text_entry_map[text.id] = entry

    for text in sorted_child_texts:
        assert text.parent_id is not None

        entry = TextEntry(text=text, children=[], author=None)
        try:
            parent = text_entry_map[text.parent_id]
            parent.children.append(entry)
        except KeyError:
            pass

    return text_entries


def create_recent_text_entries(
    all_entries: list[TextEntry] | None = None,
) -> list[TextEntry]:
    if all_entries is None:
        all_entries = create_text_entries()
    recent = [e for e in all_entries if e.text.published_at is not None]
    recent.sort(key=lambda e: e.text.published_at, reverse=True)
    return recent[:5]


@dc.dataclass
class SubGroup:
    """A subheading within a top-level collection group."""

    title: str | None
    description: str | None
    entries: list[TextEntry]

    @property
    def text_count(self) -> int:
        return len(self.entries)

    @property
    def most_recent(self) -> "TextEntry | None":
        latest = None
        for e in self.entries:
            pub = e.text.published_at
            if pub and (latest is None or pub > latest.text.published_at):
                latest = e
        return latest


@dc.dataclass
class CollectionGroup:
    """A top-level collection with its description and subgroups."""

    title: str
    description: str | None
    subgroups: list[SubGroup]

    @property
    def text_count(self) -> int:
        return sum(len(sg.entries) for sg in self.subgroups)

    @property
    def most_recent(self) -> TextEntry | None:
        latest = None
        for sg in self.subgroups:
            for e in sg.entries:
                pub = e.text.published_at
                if pub and (latest is None or pub > latest.text.published_at):
                    latest = e
        return latest


def create_grouped_text_entries(
    all_entries: list[TextEntry] | None = None,
) -> list[CollectionGroup]:
    """Group text entries by collections two levels deep.

    Top-level collections become major headings.  Their direct children
    become subheadings.  Deeper descendants are folded into the nearest
    depth-2 ancestor.  Texts that don't belong to any collection land in
    a fallback group.
    """
    all_colls = q.Query(q.get_session()).all_collections()
    by_parent = q.group_collections_by_parent(all_colls)
    top_collections = by_parent.get(None, [])

    # Map every collection id → (top_title, sub_title_or_None).
    # depth-1 = top-level collection (sub_title=None, texts go under heading directly)
    # depth-2 = direct child (sub_title=child.title)
    # depth-3+ = folded into its depth-2 ancestor
    coll_id_to_key: dict[int, tuple[str, str | None]] = {}

    for top in top_collections:
        coll_id_to_key[top.id] = (top.title, None)
        for child in by_parent.get(top.id, []):
            coll_id_to_key[child.id] = (top.title, child.title)
            # All deeper descendants map to this child's subheading.
            for desc_id in q.all_descendant_ids(child.id, all_colls):
                if desc_id != child.id:
                    coll_id_to_key[desc_id] = (top.title, child.title)

    fallback_heading = "\u0905\u0928\u094d\u092f\u0947 \u0917\u094d\u0930\u0928\u094d\u0925\u093e\u0903"  # अन्ये ग्रन्थाः

    # Build ordered structure: heading → {sub → entries}
    # Use (heading, sub) insertion order to preserve collection ordering.
    # Track top-level info: (title, description, [(sub_title, sub_description)])
    top_info: list[tuple[str, str | None, list[tuple[str | None, str | None]]]] = []
    bucket: dict[tuple[str, str | None], list[TextEntry]] = {}

    for top in top_collections:
        subs: list[tuple[str | None, str | None]] = [(None, None)]
        bucket[(top.title, None)] = []
        for child in by_parent.get(top.id, []):
            subs.append((child.title, child.description))
            bucket[(top.title, child.title)] = []
        top_info.append((top.title, top.description, subs))

    fallback_description = "The texts in this collection do not have a clear category or have not yet been categorized."
    top_info.append((fallback_heading, fallback_description, [(None, None)]))
    bucket[(fallback_heading, None)] = []

    if all_entries is None:
        all_entries = create_text_entries()
    for entry in all_entries:
        key = None
        # Pick the most specific (deepest) matching collection.
        for coll in entry.text.collections:
            k = coll_id_to_key.get(coll.id)
            if k:
                if key is None or (k[1] is not None and key[1] is None):
                    key = k
        if key is None:
            key = (fallback_heading, None)
        bucket[key].append(entry)

    result: list[CollectionGroup] = []
    for heading, description, subs in top_info:
        groups = []
        for sub_title, sub_desc in subs:
            entries = bucket.get((heading, sub_title), [])
            if entries:
                groups.append(
                    SubGroup(title=sub_title, description=sub_desc, entries=entries)
                )
        if groups:
            result.append(
                CollectionGroup(
                    title=heading,
                    description=description,
                    subgroups=groups,
                )
            )

    return result
