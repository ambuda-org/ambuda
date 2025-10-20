import hashlib
import io
import logging
import os
import zipfile
from dataclasses import dataclass

import config
import requests
from ambuda import database as db
from ambuda.seed.utils.itihasa_utils import CACHE_DIR
from ambuda.utils.tei_parser import Document, parse_document
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

LOG = logging.getLogger(__name__)

@dataclass
class Spec:
    slug: str
    title: str
    filename: str
    genre: db.TextGenre


def fetch_text(url: str, read_from_cache: bool = True) -> str:
    """Fetch text data against a simple cache.

    In production, we don't need the cache at all. But during development, it's
    useful to use a cache so that we can iterate on the end-to-end setup without
    waiting on network overhead.

    :param url: the URL to fetch.
    :param read_from_cache: if true, check the cache before fetching over the
        network.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    if path.exists() and read_from_cache:
        return path.read_text()

    resp = requests.get(url)
    # When the response headers don't specify any encoding, `resp.text` decodes
    # the response as if it is in ISO-8859-1 encoding (following RFC 2616).
    # This is usually incorrect, so we need to set `resp.encoding` to the
    # actual encoding (guessed using `chardet`).
    resp.encoding = resp.apparent_encoding
    path.write_text(resp.text)
    return resp.text


def fetch_bytes(url: str, read_from_cache: bool = True) -> bytes:
    """Fetch binary data against a simple cache.

    In production, we don't need the cache at all. But during development, it's
    useful to use a cache so that we can iterate on the end-to-end setup without
    waiting on network overhead.

    :param url: the URL to fetch.
    :param read_from_cache: if true, check the cache before fetching over the
        network.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    code = hashlib.sha256(url.encode()).hexdigest()
    path = CACHE_DIR / code

    if path.exists() and read_from_cache:
        return path.read_bytes()

    resp = requests.get(url)
    path.write_bytes(resp.content)
    return resp.content


def unzip_and_read(zip_bytes: bytes, filepath: str) -> str:
    """Open a ZIP archive and read plain-text data from one of its files.

    :param zip_bytes: the ZIP file payload
    :param filepath: the filepath within the ZIP file that we should read
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as ref:
        with ref.open(filepath) as f:
            return f.read()


def create_db():
    """Create a SQLAlchemy database engine."""
    flask_env = os.environ["FLASK_ENV"]
    conf = config.load_config_object(flask_env)
    engine = create_engine(conf.SQLALCHEMY_DATABASE_URI)

    db.Base.metadata.create_all(engine)
    return engine


def _create_new_text(session, spec: Spec, document: Document):
    """Create new text in the database."""
    text_genre = session.query(db.Genre).filter_by(name=spec.genre.value).first()
    text = db.Text(slug=spec.slug, title=spec.title, header=document.header, genre=text_genre)
    session.add(text)
    session.flush()

    n = 1
    for section in document.sections:
        db_section = db.TextSection(
            text_id=text.id, slug=section.slug, title=section.slug
        )
        session.add(db_section)
        session.flush()

        for block in section.blocks:
            db_block = db.TextBlock(
                text_id=text.id,
                section_id=db_section.id,
                slug=block.slug,
                xml=block.blob,
                n=n,
            )
            session.add(db_block)
            n += 1

    session.commit()


def add_document(engine, spec: Spec, document_path):
    " Add a document to the database. "

    with Session(engine) as session:  # noqa: F821
        if session.query(db.Text).filter_by(slug=spec.slug).first():
            # FIXME: update existing texts in-place so that we can capture
            # changes. As a workaround for now, we can delete then re-create.
            LOG.info(f"- Skipped {spec.slug} (already exists)")  # noqa: F821
        else:
            document = parse_document(document_path)
            _create_new_text(session, spec, document)
            LOG.info(f"- Created {spec.slug}")  # noqa: F821
