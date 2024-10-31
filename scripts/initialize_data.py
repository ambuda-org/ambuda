"""Initializes all Ambuda data.

Tasks include:

- Creating the database and initializing tables.
- Migrating the database to the latest version with Alembic.
- Seeding the DB with lookup data.
- Seeting the DB with texts, parse data, and dictionaries.
- Installing Vidyut data.

This script is conservative and runs on every deploy.
"""

import argparse
import dataclasses as dc
import logging
import os
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import alembic.command
import alembic.config
import requests
import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import ambuda.seed.dcs
import ambuda.seed.dictionaries.amarakosha
import ambuda.seed.dictionaries.apte
import ambuda.seed.dictionaries.apte_sanskrit_hindi
import ambuda.seed.dictionaries.monier
import ambuda.seed.dictionaries.shabdakalpadruma
import ambuda.seed.dictionaries.shabdartha_kaustubha
import ambuda.seed.dictionaries.shabdasagara
import ambuda.seed.dictionaries.vacaspatyam
import ambuda.seed.texts.gretil
import ambuda.seed.texts.mahabharata
import ambuda.seed.texts.ramayana
from ambuda import config, consts
from ambuda import database as db
from ambuda.enums import SitePageStatus, SiteRole

load_dotenv()

AMBUDA_DIR = Path(__file__).parent.parent


@dc.dataclass
class DictionarySpec:
    title: str
    slug: str
    runner: Callable


DICTIONARY_SPECS = [
    DictionarySpec(
        title="अमरकोशः", slug="amara", runner=ambuda.seed.dictionaries.amarakosha.run
    ),
    DictionarySpec(
        title="Apte Practical Sanskrit-English Dictionary (1890)",
        slug="apte",
        runner=ambuda.seed.dictionaries.apte.run,
    ),
    DictionarySpec(
        title="आप्टे संस्कृत-हिन्दी कोश (1966)",
        slug="apte-sh",
        runner=ambuda.seed.dictionaries.apte_sanskrit_hindi.run,
    ),
    DictionarySpec(
        title="Monier-Williams Sanskrit-English Dictionary (1899)",
        slug="mw",
        runner=ambuda.seed.dictionaries.monier.run,
    ),
    DictionarySpec(
        title="Śabdakalpadrumaḥ (1886)",
        slug="shabdakalpadruma",
        runner=ambuda.seed.dictionaries.shabdakalpadruma.run,
    ),
    DictionarySpec(
        title="Shabdarthakaustubha",
        slug="shabdartha-kaustubha",
        runner=ambuda.seed.dictionaries.shabdartha_kaustubha.run,
    ),
    DictionarySpec(
        title="Shabda-Sagara (1900)",
        slug="shabdasagara",
        runner=ambuda.seed.dictionaries.shabdasagara.run,
    ),
    DictionarySpec(
        title="Vācaspatyam (1873)",
        slug="vacaspatyam",
        runner=ambuda.seed.dictionaries.vacaspatyam.run,
    ),
]


def info(msg=""):
    logging.info(msg)


def header(text):
    info()
    info("-" * 50)
    info(text)
    info("-" * 50)


def create_or_upgrade_database(engine):
    """If the database does not exist, create all tables and mark it as the
    latest Alembic version.

    If the database does exist, upgrade it to the latest Alembic version.
    """
    alembic_ini = AMBUDA_DIR / "alembic.ini"
    assert alembic_ini.exists()
    alembic_cfg = alembic.config.Config(alembic_ini)

    insp = sa.inspect(engine)
    db_exists = insp.has_table("users")

    if db_exists:
        info("Database exists. Upgrading ...")
        alembic.command.upgrade(alembic_cfg, "head")
        info("Upgraded to latest Alembic revision.")
    else:
        info("Database not found. Initializing ...")
        db.Base.metadata.create_all(engine)
        alembic.command.ensure_version(alembic_cfg)
        alembic.command.stamp(alembic_cfg, "head")
        info("Marked database as latest Alembic revision.")


def sync_user_roles(engine):
    """Create roles iff they don't exist already."""

    info("Syncing SiteRole ...")
    with Session(engine) as session:
        roles = session.query(db.Role).all()
        existing_names = {s.name for s in roles}
        new_names = {r.value for r in SiteRole if r.value not in existing_names}

        if new_names:
            for name in new_names:
                status = db.Role(name=name)
                session.add(status)
                info(f"Created role: {name}")
            session.commit()


def sync_page_statuses(engine):
    """Create page statuses iff they don't exist already."""

    info("Syncing PageStatus ...")
    with Session(engine) as session:
        statuses = session.query(db.PageStatus).all()
        existing_names = {s.name for s in statuses}
        new_names = {n.value for n in SitePageStatus if n not in existing_names}

        if new_names:
            for name in new_names:
                status = db.PageStatus(name=name)
                session.add(status)
            session.commit()


def sync_bot_user(engine):
    """Create a simple bot user for various proofing commands."""

    info("Syncing bot user ...")
    try:
        bot_password = os.environ["AMBUDA_BOT_PASSWORD"]
    except KeyError as e:
        raise ValueError(
            "Please set the AMBUDA_BOT_PASSWORD environment variable."
        ) from e

    with Session(engine) as session:
        user = session.query(db.User).filter_by(username=consts.BOT_USERNAME).first()
        if user:
            return

        user = db.User(username=consts.BOT_USERNAME, email="bot@ambuda.org")
        user.set_password(bot_password)
        session.add(user)
        session.commit()


def sync_vidyut_data():
    info("Syncing Vidyut data ...")

    data_url = (
        "https://github.com/ambuda-org/vidyut-py/releases/download/0.2.0/data-0.2.0.zip"
    )
    vidyut_data_folder = Path(os.environ["VIDYUT_DATA_FOLDER"])

    if vidyut_data_folder.exists():
        info("Reusing existing Vidyut data (see $VIDYUT_DATA_FOLDER) ...")
    else:
        info("No Vidyut data found. Fetching ...")

        with requests.get(data_url, stream=True) as r:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_zip = Path(temp_dir) / "vidyut.zip"

                # https://stackoverflow.com/questions/16694907/download-large-file-in-python-with-requests
                info(f"Writing data to tempfile ({temp_zip}) ...")
                with open(temp_zip, "wb") as f:
                    shutil.copyfileobj(r.raw, f)

                vidyut_data_folder.parent.mkdir(exist_ok=True)
                info(f"created {vidyut_data_folder.parent}")
                with zipfile.ZipFile(temp_zip, "r") as f_zip:
                    f_zip.extractall(vidyut_data_folder.parent)
                    # TODO: extracted folder is called `data-0.2.0`, see if we
                    # can avoid this in the future.
                    Path(vidyut_data_folder.parent / "data-0.2.0").rename(
                        vidyut_data_folder
                    )

        info(f"Extracted data to {vidyut_data_folder}.")


def run():
    class Mode:
        CORE = "core"
        SAMPLE = "sample"
        ALL = "all"

    # core: initialize core data (enums, Vidyut)
    # sample: core + some interesting sample data
    # all: core + all texts, dictionaries, etc.
    parser = argparse.ArgumentParser(
        prog="initialize_data", description="Initializes all Ambuda data and tables."
    )
    parser.add_argument(
        "--mode", choices=[Mode.CORE, Mode.SAMPLE, Mode.ALL], required=True, help=""
    )
    args = parser.parse_args()

    flask_env = os.environ["FLASK_ENV"]
    conf = config.load_config_object(flask_env)

    # Begin
    # ---------------
    logging.getLogger().setLevel(0)
    info("Initializing application data for Ambuda.")

    header("Database and schemas")
    if conf.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        file_path = conf.SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")
        # TODO: Windows support?
        if file_path.startswith("/"):
            info(f"Creating parent directories for sqlite DB (path = {file_path}) ...")
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(conf.SQLALCHEMY_DATABASE_URI)
    create_or_upgrade_database(engine)
    # Reset logger config after Alembic call.
    logging.getLogger().setLevel(0)

    header("Enums and site data")
    sync_user_roles(engine)
    sync_page_statuses(engine)
    sync_bot_user(engine)

    header("Vidyut data")
    sync_vidyut_data()

    header("Texts")
    if args.mode in {Mode.SAMPLE, Mode.ALL}:
        ambuda.seed.texts.gretil.run(engine)

    if args.mode == Mode.ALL:
        ambuda.seed.texts.ramayana.run(engine)
        ambuda.seed.texts.mahabharata.run(engine)

    header("Parse data")
    if args.mode in {Mode.SAMPLE, Mode.ALL}:
        with Session(engine) as session:
            ambuda.seed.dcs.run(session)

    header("Dictionaries")
    with Session(engine) as session:
        if args.mode == Mode.SAMPLE:
            allow_list = {"apte"}
        elif args.mode == Mode.ALL:
            allow_list = {d.slug for d in DICTIONARY_SPECS}
        else:
            allow_list = {}

        for spec in DICTIONARY_SPECS:
            slug = spec.slug
            if slug not in allow_list:
                continue

            if session.query(db.Dictionary).filter_by(slug=slug).first() is not None:
                info(f"- Skipping: {slug} (already exists)")
                continue

            spec.runner(session, spec)

    info()
    info("Complete.")


if __name__ == "__main__":
    run()
