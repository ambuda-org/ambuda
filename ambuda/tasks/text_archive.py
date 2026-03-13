"""Celery task for exporting texts as a ZIP archive to S3."""

import json
import logging
import tempfile
import zipfile
from pathlib import Path

from ambuda import database as db
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session
from ambuda.utils.s3 import S3Path
from ambuda.utils.text_exports import ExportType, create_xml_file
from ambuda.utils.text_utils import text_metadata


logger = logging.getLogger(__name__)


def create_text_archive_inner(text_ids, app_environment, engine=None):
    """Create a ZIP archive of selected texts and upload to S3.

    For each text, the ZIP contains:
    - {slug}.xml — TEI XML (downloaded from S3 if available, otherwise generated)
    - metadata.json — metadata for all included texts
    """
    with get_db_session(app_environment, engine=engine) as (session, q, config_obj):
        texts = []
        for text_id in text_ids:
            text = session.get(db.Text, text_id)
            if text:
                texts.append(text)

        if not texts:
            logger.warning("No valid texts found for archive")
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            metadata = []

            for text in texts:
                xml_out_path = temp_dir_path / f"{text.slug}.xml"

                xml_export = (
                    session.query(db.TextExport)
                    .filter(
                        db.TextExport.text_id == text.id,
                        db.TextExport.export_type == ExportType.XML,
                    )
                    .first()
                )

                if xml_export and xml_export.s3_path:
                    try:
                        s3_path = S3Path.from_path(xml_export.s3_path)
                        s3_path.download_file(xml_out_path)
                        logger.info(f"Downloaded XML for {text.slug} from S3")
                    except Exception as e:
                        logger.warning(
                            f"Failed to download XML for {text.slug} from S3: {e}. "
                            "Falling back to generation."
                        )
                        create_xml_file(text, xml_out_path)
                else:
                    create_xml_file(text, xml_out_path)

                metadata.append(text_metadata(text))

            metadata_path = temp_dir_path / "metadata.json"
            metadata_path.write_text(
                json.dumps(metadata, indent=2, ensure_ascii=False)
            )

            zip_path = temp_dir_path / "all-texts.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for entry in metadata:
                    xml_file = temp_dir_path / f"{entry['slug']}.xml"
                    if xml_file.exists():
                        zf.write(xml_file, xml_file.name)
                zf.write(metadata_path, "metadata.json")

            bucket = config_obj.S3_BUCKET
            s3_path = S3Path(bucket, "assets/bulk/all-texts.zip")
            s3_path.upload_file(zip_path)
            logger.info(f"Uploaded text archive to {s3_path}")


@app.task(bind=True)
def create_text_archive(self, text_ids, app_environment):
    create_text_archive_inner(text_ids, app_environment)
