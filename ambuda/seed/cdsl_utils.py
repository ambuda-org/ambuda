import io
import itertools
from xml.etree import ElementTree as ET

from sqlalchemy.orm import Session

import ambuda.database as db


def iter_entries_as_xml(blob: str):
    """Iterate over CDSL-style dictionary XML."""
    tag_str = (
        "H1 H1A H1B H1C H1E H2 H2A H2B H2C H2E " "H3 H3A H3B H3C H3E H4 H4A H4B H4C H4E"
    )
    allowed_tags = set(tag_str.split())

    for _, elem in ET.iterparse(io.BytesIO(blob), events=["end"]):
        if elem.tag not in allowed_tags:
            continue

        # NOTE: `key` is not unique.
        key = None
        for child in elem.iter():
            if child.tag == "key1":
                key = child.text
                break
        yield key, elem

        elem.clear()


def iter_entries_as_strings(blob: str):
    for key, elem in iter_entries_as_xml(blob):
        value = ET.tostring(elem, encoding="utf-8")

        assert key and value
        assert len(value) > 50, value
        yield key, value


def create_dict(session, **kw):
    """Create a new dictionary."""
    dictionary = db.Dictionary(**kw)
    session.add(dictionary)
    session.commit()
    return dictionary


def delete_existing_dict(session, slug: str):
    """Delete an existing dictionary and all of its entries."""
    dictionary = session.query(db.Dictionary).filter_by(slug=slug).first()
    if dictionary:
        # Delete entries first to avoid slow relationship-based delete.
        session.query(db.DictionaryEntry).filter_by(
            dictionary_id=dictionary.id
        ).delete()
        session.delete(dictionary)
        session.commit()


def batches(generator, n):
    while True:
        batch = list(itertools.islice(generator, n))
        if batch:
            yield batch
        else:
            return


def create_from_scratch(engine, slug: str, title: str, generator):
    with Session(engine) as session:
        delete_existing_dict(session, slug)
        dictionary = create_dict(session, slug=slug, title=title)
        dictionary_id = dictionary.id
        assert dictionary_id

    entries = db.DictionaryEntry.__table__
    ins = entries.insert()
    with engine.connect() as conn:
        for i, batch in enumerate(batches(generator, 10000)):
            items = []
            for key, value in batch:
                items.append(
                    {"dictionary_id": dictionary.id, "key": key, "value": value}
                )
            conn.execute(ins, items)
            print(10000 * (i + 1))
