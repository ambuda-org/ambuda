"""Unit tests for ambuda.tasks.text_archive.

All DB, S3, and XML-generation calls are mocked so these tests
never touch the filesystem or network.
"""

import json
import zipfile
from unittest.mock import MagicMock, patch

from ambuda.tasks.text_archive import create_text_archive_inner


def _make_text(
    id=1,
    slug="test-text",
    title="Test Text",
    header="<teiHeader/>",
    config=None,
    language="sa",
    status="published",
    genre_name=None,
    collection_slugs=None,
):
    text = MagicMock()
    text.id = id
    text.slug = slug
    text.title = title
    text.header = header
    text.config = json.dumps(config) if config else None
    text.language = language
    text.status = status

    if genre_name:
        text.genre.name = genre_name
    else:
        text.genre = None

    text.collections = []
    for cs in collection_slugs or []:
        c = MagicMock()
        c.slug = cs
        text.collections.append(c)

    return text


def _make_text_export(s3_path="s3://bucket/assets/text-exports/test-text.xml"):
    export = MagicMock()
    export.export_type = "xml"
    export.s3_path = s3_path
    return export


def _setup_db_session(texts_by_id, exports_by_text_id=None):
    """Return a (session, q, config) triple with the given texts queryable."""
    session = MagicMock()
    session.get = lambda model, tid: texts_by_id.get(tid)

    exports = exports_by_text_id or {}

    def fake_query(model):
        q = MagicMock()

        def fake_filter(*args, **kwargs):
            fq = MagicMock()
            for text_id, export in exports.items():
                fq.first.return_value = export
                return fq
            fq.first.return_value = None
            return fq

        q.filter.return_value = q
        q.filter.side_effect = fake_filter
        return q

    session.query.side_effect = fake_query

    config = MagicMock()
    config.S3_BUCKET = "test-bucket"

    return session, MagicMock(), config


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_metadata_fields(mock_get_db, mock_create_xml, mock_s3_cls):
    """metadata.json contains correct fields for each text."""
    text = _make_text(
        id=1,
        slug="gita",
        title="Bhagavad Gita",
        header="<teiHeader/>",
        config={"headings": "chapter"},
        language="sa",
        status="published",
        genre_name="kavya",
        collection_slugs=["itihasa", "classics"],
    )
    session, q, cfg = _setup_db_session({1: text})
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    uploaded = {}

    def capture_upload(path):
        with zipfile.ZipFile(path, "r") as zf:
            uploaded["names"] = zf.namelist()
            uploaded["metadata"] = json.loads(zf.read("metadata.json"))

    mock_s3_instance = MagicMock()
    mock_s3_instance.upload_file.side_effect = capture_upload
    mock_s3_cls.return_value = mock_s3_instance

    create_text_archive_inner([1], "testing")

    assert len(uploaded["metadata"]) == 1
    m = uploaded["metadata"][0]
    assert m["slug"] == "gita"
    assert m["title"] == "Bhagavad Gita"
    assert m["header"] == "<teiHeader/>"
    assert m["config"] == {"headings": "chapter"}
    assert m["language"] == "sa"
    assert m["status"] == "published"
    assert m["genre"] == "kavya"
    assert m["collections"] == ["itihasa", "classics"]


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_downloads_from_s3_when_export_exists(mock_get_db, mock_create_xml, mock_s3_cls):
    """When a TextExport with s3_path exists, downloads XML from S3."""
    text = _make_text(id=1, slug="gita")
    export = _make_text_export("s3://bucket/assets/text-exports/gita.xml")
    session, q, cfg = _setup_db_session({1: text}, {1: export})
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    mock_s3_from_path = MagicMock()
    mock_s3_cls.from_path.return_value = mock_s3_from_path

    def fake_download(path):
        path.write_text("<TEI/>")

    mock_s3_from_path.download_file.side_effect = fake_download

    mock_s3_cls.return_value = MagicMock()

    create_text_archive_inner([1], "testing")

    mock_s3_cls.from_path.assert_called_once_with("s3://bucket/assets/text-exports/gita.xml")
    mock_s3_from_path.download_file.assert_called_once()
    mock_create_xml.assert_not_called()


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_falls_back_to_generate_when_no_export(mock_get_db, mock_create_xml, mock_s3_cls):
    """When no TextExport exists, falls back to create_xml_file."""
    text = _make_text(id=1, slug="gita")
    session, q, cfg = _setup_db_session({1: text}, {})  # no exports
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    def fake_create_xml(t, path):
        path.write_text("<TEI/>")

    mock_create_xml.side_effect = fake_create_xml
    mock_s3_cls.return_value = MagicMock()

    create_text_archive_inner([1], "testing")

    mock_create_xml.assert_called_once()
    assert mock_create_xml.call_args[0][0] is text


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_falls_back_on_s3_download_failure(mock_get_db, mock_create_xml, mock_s3_cls):
    """When S3 download fails, falls back to create_xml_file."""
    text = _make_text(id=1, slug="gita")
    export = _make_text_export("s3://bucket/assets/text-exports/gita.xml")
    session, q, cfg = _setup_db_session({1: text}, {1: export})
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    mock_s3_from_path = MagicMock()
    mock_s3_from_path.download_file.side_effect = Exception("S3 is down")
    mock_s3_cls.from_path.return_value = mock_s3_from_path

    def fake_create_xml(t, path):
        path.write_text("<TEI/>")

    mock_create_xml.side_effect = fake_create_xml
    mock_s3_cls.return_value = MagicMock()

    create_text_archive_inner([1], "testing")

    mock_create_xml.assert_called_once()


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_no_texts_skips_upload(mock_get_db, mock_create_xml, mock_s3_cls):
    """When all text_ids are invalid, no ZIP is created or uploaded."""
    session, q, cfg = _setup_db_session({})  # no texts
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    create_text_archive_inner([999], "testing")

    mock_create_xml.assert_not_called()
    mock_s3_cls.assert_not_called()


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_upload_destination(mock_get_db, mock_create_xml, mock_s3_cls):
    """ZIP is uploaded to the correct S3 bucket and key."""
    text = _make_text(id=1, slug="gita")
    session, q, cfg = _setup_db_session({1: text})
    cfg.S3_BUCKET = "my-bucket"
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    def fake_create_xml(t, path):
        path.write_text("<TEI/>")

    mock_create_xml.side_effect = fake_create_xml

    mock_s3_instance = MagicMock()
    mock_s3_cls.return_value = mock_s3_instance

    create_text_archive_inner([1], "testing")

    mock_s3_cls.assert_called_once_with("my-bucket", "assets/bulk/all-texts.zip")
    mock_s3_instance.upload_file.assert_called_once()


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_zip_contains_xml_and_metadata(mock_get_db, mock_create_xml, mock_s3_cls):
    """The uploaded ZIP contains XML files and metadata.json."""
    texts = {
        1: _make_text(id=1, slug="gita", title="Gita"),
        2: _make_text(id=2, slug="ramayana", title="Ramayana"),
    }
    session, q, cfg = _setup_db_session(texts)
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    def fake_create_xml(t, path):
        path.write_text(f"<TEI>{t.slug}</TEI>")

    mock_create_xml.side_effect = fake_create_xml

    uploaded = {}

    def capture_upload(path):
        with zipfile.ZipFile(path, "r") as zf:
            uploaded["names"] = sorted(zf.namelist())
            uploaded["metadata"] = json.loads(zf.read("metadata.json"))

    mock_s3_instance = MagicMock()
    mock_s3_instance.upload_file.side_effect = capture_upload
    mock_s3_cls.return_value = mock_s3_instance

    create_text_archive_inner([1, 2], "testing")

    assert uploaded["names"] == ["gita.xml", "metadata.json", "ramayana.xml"]
    assert len(uploaded["metadata"]) == 2
    slugs = [m["slug"] for m in uploaded["metadata"]]
    assert "gita" in slugs
    assert "ramayana" in slugs


@patch("ambuda.tasks.text_archive.S3Path")
@patch("ambuda.tasks.text_archive.create_xml_file")
@patch("ambuda.tasks.text_archive.get_db_session")
def test_null_config_in_metadata(mock_get_db, mock_create_xml, mock_s3_cls):
    """Text with config=None produces null in metadata, not a parse error."""
    text = _make_text(id=1, slug="gita", config=None)
    session, q, cfg = _setup_db_session({1: text})
    mock_get_db.return_value.__enter__ = MagicMock(return_value=(session, q, cfg))
    mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

    def fake_create_xml(t, path):
        path.write_text("<TEI/>")

    mock_create_xml.side_effect = fake_create_xml

    uploaded = {}

    def capture_upload(path):
        with zipfile.ZipFile(path, "r") as zf:
            uploaded["metadata"] = json.loads(zf.read("metadata.json"))

    mock_s3_instance = MagicMock()
    mock_s3_instance.upload_file.side_effect = capture_upload
    mock_s3_cls.return_value = mock_s3_instance

    create_text_archive_inner([1], "testing")

    assert uploaded["metadata"][0]["config"] is None
