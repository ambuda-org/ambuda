"""Tests for create_text_from_document and update_text_from_document."""

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

import ambuda.database as db
import ambuda.data_utils as data_utils
from ambuda.queries import get_session
from ambuda.utils.tei_parser import Block, Document, Section


def _doc(sections, header=""):
    """Build a Document from [(section_slug, [(block_slug, block_xml), ...]), ...]."""
    return Document(
        header=header,
        sections=[
            Section(slug=s, blocks=[Block(slug=bs, blob=bx) for bs, bx in blks])
            for s, blks in sections
        ],
    )


def _block_map(session, text_id):
    """Return {slug: (id, xml)} for all blocks of a text, ordered by n."""
    blocks = (
        session.execute(
            select(db.TextBlock)
            .where(db.TextBlock.text_id == text_id)
            .order_by(db.TextBlock.n)
        )
        .scalars()
        .all()
    )
    return {b.slug: (b.id, b.xml) for b in blocks}


def _section_slugs(session, text_id):
    """Return section slugs in order."""
    sections = (
        session.execute(
            select(db.TextSection)
            .where(db.TextSection.text_id == text_id)
            .order_by(db.TextSection.order)
        )
        .scalars()
        .all()
    )
    return [s.slug for s in sections]


def _create_and_reload(session, slug, doc):
    """Create a text, then re-fetch with sections eager-loaded."""
    text = data_utils.create_text_from_document(session, slug, "Original", doc)
    session.expire_all()
    return session.execute(
        select(db.Text).filter_by(id=text.id).options(selectinload(db.Text.sections))
    ).scalar_one()


def _cleanup(session, text):
    session.execute(delete(db.BlockParse).where(db.BlockParse.text_id == text.id))
    session.delete(text)
    session.commit()


# -- create_text_from_document --


def test_create_basic(flask_app):
    with flask_app.app_context():
        session = get_session()
        doc = _doc([("ch1", [("1.1", "<p>aaa</p>"), ("1.2", "<p>bbb</p>")])])
        text = data_utils.create_text_from_document(session, "test-create", "Test", doc)

        assert text.id is not None
        assert text.slug == "test-create"
        assert _section_slugs(session, text.id) == ["ch1"]
        bm = _block_map(session, text.id)
        assert list(bm.keys()) == ["1.1", "1.2"]
        assert bm["1.1"][1] == "<p>aaa</p>"

        _cleanup(session, text)


def test_create_multiple_sections(flask_app):
    with flask_app.app_context():
        session = get_session()
        doc = _doc(
            [
                ("ch1", [("1.1", "<p>a</p>")]),
                ("ch2", [("2.1", "<p>b</p>"), ("2.2", "<p>c</p>")]),
            ]
        )
        text = data_utils.create_text_from_document(
            session, "test-multi-sec", "Test", doc
        )

        assert _section_slugs(session, text.id) == ["ch1", "ch2"]
        bm = _block_map(session, text.id)
        assert list(bm.keys()) == ["1.1", "2.1", "2.2"]

        _cleanup(session, text)


# -- update_text_from_document --


def test_update_preserves_text_id(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session, "test-upd-id", _doc([("ch1", [("1.1", "<p>old</p>")])])
        )
        original_id = text.id

        doc_v2 = _doc([("ch1", [("1.1", "<p>new</p>")])])
        data_utils.update_text_from_document(session, text, "Updated", doc_v2)

        assert text.id == original_id
        assert text.title == "Updated"

        _cleanup(session, text)


def test_update_preserves_block_ids(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session,
            "test-upd-blk",
            _doc([("ch1", [("1.1", "<p>old</p>"), ("1.2", "<p>keep</p>")])]),
        )
        old_blocks = _block_map(session, text.id)
        old_id_1 = old_blocks["1.1"][0]
        old_id_2 = old_blocks["1.2"][0]

        doc_v2 = _doc([("ch1", [("1.1", "<p>changed</p>"), ("1.2", "<p>keep</p>")])])
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        new_blocks = _block_map(session, text.id)
        assert new_blocks["1.1"][0] == old_id_1
        assert new_blocks["1.2"][0] == old_id_2
        assert new_blocks["1.1"][1] == "<p>changed</p>"
        assert new_blocks["1.2"][1] == "<p>keep</p>"

        _cleanup(session, text)


def test_update_preserves_parse_data(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session, "test-upd-parse", _doc([("ch1", [("1.1", "<p>old</p>")])])
        )
        block_id = _block_map(session, text.id)["1.1"][0]

        parse = db.BlockParse(text_id=text.id, block_id=block_id, data="x\ty\tpos=n")
        session.add(parse)
        session.commit()
        parse_id = parse.id

        doc_v2 = _doc([("ch1", [("1.1", "<p>new</p>")])])
        text = session.execute(
            select(db.Text)
            .filter_by(id=text.id)
            .options(selectinload(db.Text.sections))
        ).scalar_one()
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        parse = session.get(db.BlockParse, parse_id)
        assert parse is not None
        assert parse.block_id == block_id
        assert parse.data == "x\ty\tpos=n"

        _cleanup(session, text)


def test_update_removes_deleted_blocks(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session,
            "test-upd-del",
            _doc([("ch1", [("1.1", "<p>a</p>"), ("1.2", "<p>b</p>")])]),
        )
        old_id = _block_map(session, text.id)["1.2"][0]

        doc_v2 = _doc([("ch1", [("1.1", "<p>a</p>")])])
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        assert "1.2" not in _block_map(session, text.id)
        assert session.get(db.TextBlock, old_id) is None

        _cleanup(session, text)


def test_update_adds_new_blocks(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session, "test-upd-add", _doc([("ch1", [("1.1", "<p>a</p>")])])
        )

        doc_v2 = _doc([("ch1", [("1.1", "<p>a</p>"), ("1.2", "<p>new</p>")])])
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        bm = _block_map(session, text.id)
        assert list(bm.keys()) == ["1.1", "1.2"]
        assert bm["1.2"][1] == "<p>new</p>"

        _cleanup(session, text)


def test_update_adds_new_section(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session, "test-upd-sec-add", _doc([("ch1", [("1.1", "<p>a</p>")])])
        )

        doc_v2 = _doc(
            [
                ("ch1", [("1.1", "<p>a</p>")]),
                ("ch2", [("2.1", "<p>b</p>")]),
            ]
        )
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        assert _section_slugs(session, text.id) == ["ch1", "ch2"]
        assert "2.1" in _block_map(session, text.id)

        _cleanup(session, text)


def test_update_removes_section(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session,
            "test-upd-sec-del",
            _doc(
                [
                    ("ch1", [("1.1", "<p>a</p>")]),
                    ("ch2", [("2.1", "<p>b</p>")]),
                ]
            ),
        )
        old_id = _block_map(session, text.id)["2.1"][0]

        doc_v2 = _doc([("ch1", [("1.1", "<p>a</p>")])])
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        assert _section_slugs(session, text.id) == ["ch1"]
        assert session.get(db.TextBlock, old_id) is None

        _cleanup(session, text)


def test_update_moves_block_to_new_section(flask_app):
    with flask_app.app_context():
        session = get_session()
        text = _create_and_reload(
            session,
            "test-upd-move",
            _doc([("ch1", [("1.1", "<p>a</p>"), ("1.2", "<p>b</p>")])]),
        )
        old_id = _block_map(session, text.id)["1.2"][0]

        doc_v2 = _doc(
            [
                ("ch1", [("1.1", "<p>a</p>")]),
                ("ch2", [("1.2", "<p>b</p>")]),
            ]
        )
        data_utils.update_text_from_document(session, text, "V2", doc_v2)

        bm = _block_map(session, text.id)
        assert bm["1.2"][0] == old_id

        block = session.get(db.TextBlock, old_id)
        ch2 = session.execute(
            select(db.TextSection).where(
                db.TextSection.text_id == text.id,
                db.TextSection.slug == "ch2",
            )
        ).scalar_one()
        assert block.section_id == ch2.id

        _cleanup(session, text)
