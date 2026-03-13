import dataclasses as dc
import json
from collections import OrderedDict
from datetime import datetime, timedelta

from vidyut.lipi import transliterate, Scheme

import ambuda.database as db
from ambuda import queries as q


def text_metadata(text: db.Text) -> dict:
    """Return a metadata dict for a single text."""
    return {
        "slug": text.slug,
        "title": text.title,
        "header": text.header,
        "config": json.loads(text.config) if text.config else None,
        "genre": text.genre.name if text.genre else None,
        "language": text.language,
        "status": text.status,
        "collections": [c.slug for c in text.collections],
    }


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


def create_recent_text_entries() -> list[TextEntry]:
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


def create_grouped_text_entries() -> list[CollectionGroup]:
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

    for entry in create_text_entries():
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
