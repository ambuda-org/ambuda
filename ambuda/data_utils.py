"""Utilities for ingesting data assets into Ambuda."""

import itertools
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, load_only

import ambuda.database as db
import ambuda.queries as q

#: The maximum number of entries to add to the dictionary at one time.
#: Batching is more efficient than adding entries one at a time. But large
#: batches also take up a lot of memory.
BATCH_SIZE = 10000


def _batches(generator, n):
    """Yield successive n-sized batches from a generator."""
    while True:
        batch = list(itertools.islice(generator, n))
        if batch:
            yield batch
        else:
            return


def create_text_from_document(session: Session, slug: str, title: str, document):
    from ambuda.models.texts import TextStage

    text = db.Text(
        slug=slug, title=title, header=document.header, stage=TextStage.PUBLIC
    )
    session.add(text)
    session.flush()
    text_id = text.id

    # Bulk-insert sections and collect their IDs.
    section_rows = [
        {"text_id": text_id, "slug": s.slug, "title": s.slug, "order": i}
        for i, s in enumerate(document.sections)
    ]
    if section_rows:
        result = session.execute(
            insert(db.TextSection).returning(db.TextSection.id), section_rows
        )
        section_ids = [row[0] for row in result]
    else:
        section_ids = []

    # Bulk-insert all blocks across all sections.
    block_rows = []
    n = 1
    for section, section_id in zip(document.sections, section_ids):
        for block in section.blocks:
            block_rows.append(
                {
                    "text_id": text_id,
                    "section_id": section_id,
                    "slug": block.slug,
                    "xml": block.blob,
                    "n": n,
                }
            )
            n += 1

    if block_rows:
        session.execute(insert(db.TextBlock), block_rows)

    session.commit()
    return text


def update_text_from_document(session: Session, text: db.Text, title: str, document):
    """Update an existing text in-place from a parsed TEI document.

    Preserves the Text row (and its ID). Sections and blocks are synced:
    existing rows are updated, new rows are inserted, removed rows are deleted.
    """
    text.title = title
    text.header = document.header

    # -- Sync sections --
    existing_sections = {s.slug: s for s in text.sections}
    doc_section_slugs = {s.slug for s in document.sections}

    # Delete removed sections (cascade deletes their blocks).
    for slug in set(existing_sections) - doc_section_slugs:
        session.delete(existing_sections[slug])

    # Create new sections, update order on existing ones.
    section_map: dict[str, db.TextSection] = {}
    for i, doc_section in enumerate(document.sections):
        if doc_section.slug in existing_sections:
            sec = existing_sections[doc_section.slug]
            sec.order = i
            section_map[doc_section.slug] = sec
        else:
            sec = db.TextSection(
                text_id=text.id,
                slug=doc_section.slug,
                title=doc_section.slug,
                order=i,
            )
            session.add(sec)
            section_map[doc_section.slug] = sec
    session.flush()

    # -- Sync blocks --
    # Match existing blocks by slug so that block IDs (and associated
    # parse data / tokens) are preserved when content changes.
    existing_blocks = (
        session.execute(
            select(db.TextBlock)
            .where(db.TextBlock.text_id == text.id)
            .order_by(db.TextBlock.n)
        )
        .scalars()
        .all()
    )
    existing_by_slug: dict[str, db.TextBlock] = {b.slug: b for b in existing_blocks}

    new_block_slugs: set[str] = set()
    insert_rows = []
    n = 1
    for doc_section in document.sections:
        section_id = section_map[doc_section.slug].id
        for block in doc_section.blocks:
            new_block_slugs.add(block.slug)
            existing = existing_by_slug.get(block.slug)
            if existing:
                existing.xml = block.blob
                existing.n = n
                existing.section_id = section_id
            else:
                insert_rows.append(
                    {
                        "text_id": text.id,
                        "section_id": section_id,
                        "slug": block.slug,
                        "xml": block.blob,
                        "n": n,
                    }
                )
            n += 1

    # Delete blocks that no longer exist.
    removed_ids = [b.id for b in existing_blocks if b.slug not in new_block_slugs]
    if removed_ids:
        session.execute(delete(db.TextBlock).where(db.TextBlock.id.in_(removed_ids)))

    if insert_rows:
        session.execute(insert(db.TextBlock), insert_rows)

    session.commit()
    return text


def drop_existing_parse_data(session: Session, text_id: int):
    stmt = select(db.BlockParse).filter_by(text_id=text_id)
    for parse in session.scalars(stmt).all():
        session.delete(parse)


def get_slug_id_map(session: Session, text_id: int) -> dict[str, int]:
    stmt = (
        select(db.TextBlock)
        .filter_by(text_id=text_id)
        .options(
            load_only(
                db.TextBlock.id,
                db.TextBlock.slug,
            )
        )
    )
    blocks = list(session.scalars(stmt).all())
    return {b.slug: b.id for b in blocks}


def iter_parse_data(path: Path) -> Iterator[tuple[str, str]]:
    block_slug = None
    buf = []
    with open(path) as f:
        for line in f:
            line = line.strip()

            if line.startswith("#"):
                comm, key, eq, value = line.split()
                if key == "id":
                    xml_id = value
                    _, _, block_slug = xml_id.partition(".")
            elif line:
                if line.count("\t") != 2:
                    raise ValueError(f'Line "{line}" must have exactly two tabs.')
                buf.append(line)
            else:
                yield block_slug, "\n".join(buf)
                buf = []
    if buf:
        yield block_slug, "\n".join(buf)


def add_parse_data(session: Session, text_slug: str, path: Path):
    stmt = select(db.Text).filter_by(slug=text_slug)
    text = session.scalars(stmt).first()
    if not text:
        raise ValueError(f"Text with slug '{text_slug}' not found")

    drop_existing_parse_data(session, text.id)

    slug_id_map = get_slug_id_map(session, text.id)
    for slug, blob in iter_parse_data(path):
        if slug not in slug_id_map:
            raise ValueError(f"Block slug '{slug}' not found in text '{text_slug}'")
        session.add(
            db.BlockParse(text_id=text.id, block_id=slug_id_map[slug], data=blob)
        )
    session.commit()


def import_dictionary_from_xml(slug: str, title: str, path: Path) -> int:
    """Import dictionary entries from an XML file using batch inserts."""

    # Create the dictionary.
    session = q.get_session()
    dictionary = db.Dictionary(slug=slug, title=title)
    session.add(dictionary)
    try:
        session.commit()
        session.close()  # New session in case upload fails
    except SQLAlchemyError as e:
        raise ValueError(f"Failed to create dictionary with slug '{slug}': {e}")

    def _iter_entries():
        """Streaming iterator that yields (key, value) tuples."""
        for event, elem in ET.iterparse(str(path), events=["end"]):
            if elem.tag != "entry":
                continue

            key_elem = elem.find("key")
            value_elem = elem.find("value")

            if key_elem is None:
                raise ValueError("Entry missing <key> element")
            if value_elem is None:
                raise ValueError("Entry missing <value> element")

            num_children = len(value_elem)
            if num_children != 1:
                raise ValueError(
                    f"<value> should have exactly one child, got {num_children}"
                )

            key = (key_elem.text or "").strip()
            value = ET.tostring(value_elem[0])

            if not key:
                raise ValueError("Entry has empty <key>")
            if not value:
                raise ValueError("Entry has empty <value>")

            yield key, value

            # Clear to free memory
            elem.clear()

    engine = q.get_engine()
    entries_table = db.DictionaryEntry.__table__
    ins = entries_table.insert()

    entry_count = 0
    with engine.begin() as conn:
        for batch in _batches(_iter_entries(), BATCH_SIZE):
            items = [
                {"dictionary_id": dictionary_id, "key": key, "value": value}
                for key, value in batch
            ]
            conn.execute(ins, items)
            entry_count += len(items)

    return entry_count


def import_text_metadata(
    session: Session, metadata: "LibraryMetadata"
) -> tuple[int, list[str]]:
    # Build author map so texts can reference them.
    author_map: dict[str, db.Author] = {}
    for a in session.scalars(select(db.Author)).all():
        author_map[a.slug] = a

    # Build/update collections first so texts can reference them.
    collection_map: dict[str, db.TextCollection] = {}
    stmt = select(db.TextCollection)
    for coll in session.scalars(stmt).all():
        collection_map[coll.slug] = coll

    for coll_entry in metadata.collections:
        if coll_entry.slug not in collection_map:
            new_coll = db.TextCollection(slug=coll_entry.slug, title=coll_entry.title)
            session.add(new_coll)
            session.flush()
            collection_map[coll_entry.slug] = new_coll
        else:
            collection_map[coll_entry.slug].title = coll_entry.title

    # Set parent references for collections.
    for coll_entry in metadata.collections:
        coll = collection_map[coll_entry.slug]
        if coll_entry.parent_slug and coll_entry.parent_slug in collection_map:
            coll.parent_id = collection_map[coll_entry.parent_slug].id
        else:
            coll.parent_id = None

    # Update texts.
    updated_count = 0
    unmatched_slugs = []

    for entry in metadata.texts:
        stmt = select(db.Text).filter_by(slug=entry.slug)
        text = session.scalars(stmt).first()

        if not text:
            unmatched_slugs.append(entry.slug)
            continue

        text.title = entry.title
        if entry.language is not None:
            text.language = entry.language
        if entry.status is not None:
            text.status = entry.status

        # Sync alternate titles.
        existing = {a.title for a in text.alternate_titles}
        for alt in entry.alternate_titles:
            if alt not in existing:
                text.alternate_titles.append(db.TextAlternateTitle(title=alt))

        # Sync author: create if missing, then assign.
        if entry.author:
            if entry.author.slug not in author_map:
                new_author = db.Author(slug=entry.author.slug, name=entry.author.name)
                session.add(new_author)
                session.flush()
                author_map[entry.author.slug] = new_author
            else:
                author_map[entry.author.slug].name = entry.author.name
            text.author = author_map[entry.author.slug]

        if entry.license is not None:
            text.license = entry.license

        # Sync collection associations.
        collections = []
        for slug in entry.collections:
            if slug in collection_map:
                collections.append(collection_map[slug])
        text.collections = collections

        updated_count += 1

    session.commit()
    return updated_count, unmatched_slugs
