import tempfile
from pathlib import Path
import uuid

import pytest

import ambuda.database as db
import ambuda.queries as q
import ambuda.tasks.text_exports as text_exports
import ambuda.tasks.utils
from ambuda.queries import get_engine, get_session
from ambuda.utils.text_exports import ExportType


_counter = 0


def _create_sample_text(session) -> db.Text:
    global _counter

    _counter += 1
    slug = f"test-text-{_counter}"
    title = f"Test Text {_counter}"
    text = db.Text(slug=slug, title=title, stage="public")
    session.add(text)
    session.flush()

    section = db.TextSection(text_id=text.id, slug="1", title="Section 1")
    session.add(section)
    session.flush()

    block = db.TextBlock(
        text_id=text.id,
        section_id=section.id,
        slug="1.1",
        xml="<lg><l>rAmaH</l><l>lakSmaNaH</l></lg>",
        n=1,
    )
    session.add(block)
    session.flush()

    return text


def test_create_xml_export_inner(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(f"{text.slug}.xml")
        assert export is not None
        assert export.text_id == text.id
        assert export.export_type == ExportType.XML
        assert export.s3_path is not None
        assert export.size > 0
        assert len(export.sha256_checksum) == 64


def test_create_plain_text_export_inner(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.txt",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(f"{text.slug}.txt")
        assert export is not None
        assert export.text_id == text.id
        assert export.export_type == ExportType.PLAIN_TEXT
        assert export.s3_path is not None
        assert export.size > 0
        assert export.sha256_checksum is not None
        assert len(export.sha256_checksum) == 64


def test_create_pdf_export_inner(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}-devanagari.pdf",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(f"{text.slug}-devanagari.pdf")
        assert export is not None
        assert export.text_id == text.id
        assert export.export_type == ExportType.PDF
        assert export.s3_path is not None
        assert export.size > 0
        assert export.sha256_checksum is not None
        assert len(export.sha256_checksum) == 64


def test_create_tokens_export_inner(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)

        section = session.query(db.TextSection).filter_by(text_id=text.id).first()
        block = session.query(db.TextBlock).filter_by(text_id=text.id).first()

        parse = db.BlockParse(
            text_id=text.id,
            block_id=block.id,
            data="rAmaH\trAma\tpos=n l=pum vi=1 va=e",
        )
        session.add(parse)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}-tokens.csv",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(f"{text.slug}-tokens.csv")
        assert export is not None
        assert export.text_id == text.id
        assert export.export_type == ExportType.TOKENS
        assert export.s3_path is not None
        assert export.size > 0
        assert export.sha256_checksum is not None
        assert len(export.sha256_checksum) == 64


def test_create_export_without_xml_fails(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        with pytest.raises(FileNotFoundError):
            text_exports.create_text_export_inner(
                text_id=text.id,
                export_key="{}.txt",
                app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
                engine=engine,
            )


def test_create_export_with_invalid_text_id(flask_app, s3_mocks):
    with flask_app.app_context():
        engine = get_engine()
        with pytest.raises(ValueError, match="Text with id 99999 not found"):
            text_exports.create_text_export_inner(
                text_id=99999,
                export_key="{}.xml",
                app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
                engine=engine,
            )


def test_create_export_with_invalid_export_type(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        with pytest.raises(ValueError, match="Unknown export type"):
            text_exports.create_text_export_inner(
                text_id=text.id,
                export_key="invalid-key",
                app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
                engine=engine,
            )


def test_update_existing_export(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export_slug = f"{text.slug}.xml"
        export = q.text_export(export_slug)
        assert export

        first_size = export.size
        first_updated_at = export.updated_at
        first_checksum = export.sha256_checksum

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(export_slug)
        assert export.size == first_size
        assert export.updated_at >= first_updated_at
        assert export.sha256_checksum == first_checksum


def test_delete_text_export(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}.xml",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export_slug = f"{text.slug}.xml"
        export = q.text_export(export_slug)
        assert export

        text_exports.delete_text_export_inner(
            export_id=export.id,
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(export_slug)
        assert export is None


def test_delete_nonexistent_export(flask_app, s3_mocks):
    with flask_app.app_context():
        engine = get_engine()

        text_exports.delete_text_export_inner(
            export_id=99999,
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )


def test_create_tokens_export_without_parse_data(flask_app, s3_mocks):
    with flask_app.app_context():
        session = get_session()
        text = _create_sample_text(session)
        session.commit()

        engine = get_engine()

        text_exports.create_text_export_inner(
            text_id=text.id,
            export_key="{}-tokens.csv",
            app_environment=flask_app.config["AMBUDA_ENVIRONMENT"],
            engine=engine,
        )

        export = q.text_export(f"{text.slug}-tokens.csv")
        assert export is None
