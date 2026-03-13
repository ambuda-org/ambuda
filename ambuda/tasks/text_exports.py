import hashlib
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from celery import chain, group

from ambuda import database as db
from ambuda.utils.s3 import S3Path
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session
from ambuda.utils import text_exports
from ambuda.utils.text_exports import (
    ExportType,
    write_cached_xml,
    delete_cached_xml,
    create_or_update_xml_export,
    create_xml_file,
    create_plain_text,
    create_pdf,
    create_epub,
    maybe_create_tokens,
    create_vocab_list,
)
from pydantic import BaseModel


EXPORTS = {x.slug_pattern: x for x in text_exports.EXPORTS}


def create_text_export_inner(
    text_id: int, export_key: str, app_environment: str, engine=None
) -> None:
    """NOTE: `engine` is exposed for testing"""
    with get_db_session(app_environment, engine=engine) as (session, q, config_obj):
        text = session.get(db.Text, text_id)
        if not text:
            raise ValueError(f"Text with id {text_id} not found")

        logging.info(f"Creating {export_key} export for {text.slug}")

        export_config = EXPORTS.get(export_key)
        if not export_config:
            raise ValueError(f"Unknown export type: {export_key}")

        needs_xml = export_config.type in (ExportType.PLAIN_TEXT, ExportType.PDF)

        # Download XML if needed, otherwise set to None
        xml_path = None
        if needs_xml:
            xml_slug = f"{text.slug}.xml"
            xml_export = q.text_export(xml_slug)

            if not xml_export:
                raise FileNotFoundError(
                    f"XML export not found for {text.slug}. "
                    "XML must be created before this export type."
                )

            if not xml_export.s3_path:
                raise ValueError(
                    f"XML export for {text.slug} exists but has no S3 path. "
                    "XML creation may have failed or is incomplete."
                )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            # Download XML if needed
            if needs_xml:
                xml_path = temp_dir_path / f"{text.slug}.xml"
                xml_s3_path = S3Path.from_path(xml_export.s3_path)
                xml_s3_path.download_file(xml_path)
                logging.info(f"Downloaded XML from {xml_s3_path} to {xml_path}")

            # Create the export file
            output_path = temp_dir_path / export_config.slug(text)

            if export_config.type == ExportType.XML:
                create_xml_file(text, output_path)
            elif export_config.type == ExportType.PLAIN_TEXT:
                assert xml_path
                create_plain_text(text, output_path, xml_path)
            elif export_config.type == ExportType.PDF:
                assert xml_path
                assert export_config.scheme
                create_pdf(
                    text,
                    output_path,
                    config_obj.S3_BUCKET,
                    xml_path,
                    export_config.scheme,
                )
            elif export_config.type == ExportType.EPUB:
                create_epub(text, output_path)
            elif export_config.type == ExportType.TOKENS:
                maybe_create_tokens(text, output_path)
            elif export_config.type == ExportType.VOCAB:
                create_vocab_list(text, output_path)
            else:
                raise ValueError(f"Unsupported export type: {export_key}")

            if not output_path.exists():
                logging.info(f"Did not create {output_path} (no data found)")
                return

            file_size = output_path.stat().st_size

            sha256_hash = hashlib.sha256()
            with open(output_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            checksum = sha256_hash.hexdigest()

            export_slug = export_config.slug(text)
            logging.info(
                f"Created {export_key} export at {output_path} (SHA256: {checksum})"
            )

            bucket = config_obj.S3_BUCKET
            key = f"assets/text-exports/{export_slug}"
            s3_path = S3Path(bucket, key)
            s3_path.upload_file(output_path)
            logging.info(f"Uploaded {export_key} export to {s3_path}")

            if export_config.type == ExportType.XML:
                write_cached_xml(
                    config_obj.SERVER_FILE_CACHE,
                    text.slug,
                    output_path,
                )

            text_export = q.text_export(export_slug)
            if text_export:
                text_export.s3_path = s3_path.path
                text_export.size = file_size
                text_export.sha256_checksum = checksum
                text_export.updated_at = datetime.now(UTC)
                logging.info(f"Updated existing TextExport: {export_slug}")
            else:
                text_export = db.TextExport(
                    text_id=text_id,
                    slug=export_slug,
                    export_type=export_config.type,
                    s3_path=s3_path.path,
                    size=file_size,
                    sha256_checksum=checksum,
                )
                session.add(text_export)
                logging.info(f"Created new TextExport: {export_slug}")
            session.commit()


@app.task(bind=True)
def create_text_export(self, text_id: int, export_key: str, app_environment: str):
    create_text_export_inner(text_id, export_key, app_environment)


@app.task(bind=True)
def upload_xml_export(self, text_id, text_slug, tei_path, app_environment):
    """Upload a TEI XML file produced by the publish flow to S3."""
    tei = Path(tei_path)
    try:
        with get_db_session(app_environment) as (session, q, cfg):
            create_or_update_xml_export(
                text_id=text_id,
                text_slug=text_slug,
                tei_path=tei,
                s3_bucket=cfg.S3_BUCKET,
                session=session,
                q=q,
                cache_dir=cfg.SERVER_FILE_CACHE,
            )
    finally:
        tei.unlink(missing_ok=True)


def delete_text_export_inner(export_id: int, app_environment: str, engine=None):
    with get_db_session(app_environment, engine=engine) as (session, query, config_obj):
        text_export = session.get(db.TextExport, export_id)
        if not text_export:
            logging.warning(f"TextExport with id {export_id} not found")
            return

        try:
            s3_path = S3Path.from_path(text_export.s3_path)
            try:
                s3_path.delete()
                logging.info(f"Deleted S3 file: {s3_path}")
            except Exception as e:
                logging.warning(f"Could not delete S3 file: {e}")

            if text_export.export_type == ExportType.XML:
                text = session.get(db.Text, text_export.text_id)
                if text:
                    delete_cached_xml(
                        config_obj.SERVER_FILE_CACHE,
                        text.slug,
                    )

            session.delete(text_export)
            session.commit()
            logging.info(f"Deleted TextExport record: {export_id}")

        except Exception as e:
            session.rollback()
            logging.error(f"Error deleting TextExport {export_id}: {e}")
            raise


@app.task(bind=True)
def delete_text_export(self, export_id: int, app_environment: str):
    delete_text_export_inner(export_id, app_environment)


def populate_file_cache_inner(app_environment: str, engine=None):
    """Download all XML exports from S3 and write them to the local file cache."""
    with get_db_session(app_environment, engine=engine) as (session, q, config_obj):
        xml_exports = (
            session.query(db.TextExport)
            .filter(db.TextExport.export_type == ExportType.XML)
            .all()
        )
        logging.info(f"Populating file cache with {len(xml_exports)} XML export(s)")

        for export in xml_exports:
            text = session.get(db.Text, export.text_id)
            if not text or not export.s3_path:
                continue

            try:
                with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
                    tmp_path = Path(tmp.name)

                s3_path = S3Path.from_path(export.s3_path)
                s3_path.download_file(tmp_path)
                write_cached_xml(config_obj.SERVER_FILE_CACHE, text.slug, tmp_path)
                logging.info(f"Cached XML for {text.slug}")
            except Exception as e:
                logging.warning(f"Failed to cache XML for {text.slug}: {e}")
            finally:
                tmp_path.unlink(missing_ok=True)


@app.task(bind=True)
def populate_file_cache(self, app_environment: str):
    populate_file_cache_inner(app_environment)


def create_all_exports_for_text(text_id: int, app_environment: str):
    xml_exports = [e for e in text_exports.EXPORTS if e.type == ExportType.XML]
    other_exports = [e for e in text_exports.EXPORTS if e.type != ExportType.XML]

    xml_task = create_text_export.si(
        text_id, xml_exports[0].slug_pattern, app_environment
    )

    other_tasks = [
        create_text_export.si(text_id, e.slug_pattern, app_environment)
        for e in other_exports
    ]

    return chain(
        xml_task,
        group(*other_tasks),
    )
