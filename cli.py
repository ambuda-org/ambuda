#!/usr/bin/env python3

import getpass
import os
from pathlib import Path

import click
from dotenv import load_dotenv
from slugify import slugify
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import ambuda
from ambuda import database as db
from ambuda import queries as q
from ambuda.models.proofing import ProjectStatus
from ambuda.seed.utils.data_utils import create_db
from ambuda.tasks.projects import (
    create_project_from_local_pdf_inner,
)
from ambuda.tasks.text_exports import create_text_export_inner
from ambuda.utils import text_exports
from ambuda.utils.text_exports import ExportType
from ambuda.tasks.utils import LocalTaskStatus
from ambuda.utils.s3 import S3Path

# Load environment variables from .env file
load_dotenv()

engine = create_db()


@click.group()
def cli():
    pass


@cli.command()
def create_user():
    """Create a new user.

    This command is best used in development to quickly create new users.
    """
    username = input("Username: ")
    raw_password = getpass.getpass("Password: ")
    email = input("Email: ")

    with Session(engine) as session:
        stmt = select(db.User).where(
            or_(db.User.username == username, db.User.email == email)
        )
        u = session.scalars(stmt).first()
        if u is not None:
            if u.username == username:
                raise click.ClickException(f'User "{username}" already exists.')
            else:
                raise click.ClickException(f'Email "{email}" already exists.')

        user = db.User(username=username, email=email)
        user.set_password(raw_password)
        session.add(user)
        session.commit()


@cli.command()
@click.option("--username", help="the user to modify")
@click.option("--role", help="the role to add")
def add_role(username, role):
    """Add the given role to the given user.

    In particular, `add-role <user> admin` will give a user administrator
    privileges and grant them full access to Ambuda's data and content.
    """
    with Session(engine) as session:
        stmt = select(db.User).where(db.User.username == username)
        u = session.scalars(stmt).first()
        if u is None:
            raise click.ClickException(f'User "{username}" does not exist.')
        stmt = select(db.Role).where(db.Role.name == role)
        r = session.scalars(stmt).first()
        if r is None:
            raise click.ClickException(f'Role "{role}" does not exist.')
        if r in u.roles:
            raise click.ClickException(f'User "{username}" already has role "{role}".')

        u.roles.append(r)
        session.add(u)
        session.commit()
    print(f'Added role "{role}" to user "{username}".')


@cli.command()
@click.option("--title", help="title of the new project")
@click.option("--pdf-path", help="path to the source PDF")
def create_project(title, pdf_path):
    """Create a proofing project from a PDF."""
    current_app = ambuda.create_app("development")
    with current_app.app_context():
        session = q.get_session()
        stmt = select(db.User)
        arbitrary_user = session.scalars(stmt).first()
        if not arbitrary_user:
            raise click.ClickException(
                "Every project must have a user that created it. "
                "But, no users were found in the database.\n"
                "Please create a user first with `create-user`."
            )

        create_project_from_local_pdf_inner(
            pdf_path=pdf_path,
            display_title=title,
            app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            creator_id=arbitrary_user.id,
            task_status=LocalTaskStatus(),
        )


@cli.command()
@click.option("--text-slug", help="slug of the text to export")
def export_text(text_slug):
    """Create all exports for a text."""
    with Session(engine) as session:
        stmt = select(db.Text).where(db.Text.slug == text_slug)
        text = session.scalars(stmt).first()
        if text is None:
            raise click.ClickException(f'Text with slug "{text_slug}" does not exist.')

        text_id = text.id

    app_environment = os.getenv("FLASK_ENV")
    if not app_environment:
        raise click.ClickException("FLASK_ENV not found in .env file")

    click.echo(
        f'Creating all exports for text "{text_slug}" (id={text_id}) in {app_environment} environment...'
    )

    xml_exports = [e for e in text_exports.EXPORTS if e.type == ExportType.XML]
    other_exports = [e for e in text_exports.EXPORTS if e.type != ExportType.XML]

    for export_config in xml_exports:
        click.echo(f"Creating {export_config.label} export...")
        create_text_export_inner(
            text_id, export_config.slug_pattern, app_environment, engine=engine
        )

    for export_config in other_exports:
        click.echo(f"Creating {export_config.label} export...")
        create_text_export_inner(
            text_id, export_config.slug_pattern, app_environment, engine=engine
        )

    click.echo("All exports completed successfully.")


BHAGAVAD_GITA_VERSES = [
    "धृतराष्ट्र उवाच ।\nधर्मक्षेत्रे कुरुक्षेत्रे समवेता युयुत्सवः ।\nमामकाः पाण्डवाश्चैव किमकुर्वत सञ्जय ॥ १-१॥",
    "सञ्जय उवाच ।\nदृष्ट्वा तु पाण्डवानीकं व्यूढं दुर्योधनस्तदा ।\nआचार्यमुपसङ्गम्य राजा वचनमब्रवीत् ॥ १-२॥",
    "पश्यैतां पाण्डुपुत्राणामाचार्य महतीं चमूम् ।\nव्यूढां द्रुपदपुत्रेण तव शिष्येण धीमता ॥ १-३॥",
    "अत्र शूरा महेष्वासा भीमार्जुनसमा युधि ।\nयुयुधानो विराटश्च द्रुपदश्च महारथः ॥ १-४॥",
    "धृष्टकेतुश्चेकितानः काशिराजश्च वीर्यवान् ।\nपुरुजित्कुन्तिभोजश्च शैब्यश्च नरपुङ्गवः ॥ १-५॥"
]


@cli.command()
def create_toy_data():
    """Create a dummy proofing project for development/onboarding."""
    import tempfile
    import fitz

    display_title = "Bhagavad Gita Sample"

    current_app = ambuda.create_app("development")
    with current_app.app_context():
        session = q.get_session()

        stmt = select(db.User)
        user = session.scalars(stmt).first()
        if not user:
            raise click.ClickException(
                "No users found in the database. "
                "Please create a user first with `create-user`."
            )

        slug = slugify(display_title)
        existing = session.scalars(select(db.Project).filter_by(slug=slug)).first()
        if existing:
            raise click.ClickException(f'Project "{display_title}" already exists.')

        pdf_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        doc = fitz.open()
        for i, verse in enumerate(BHAGAVAD_GITA_VERSES, start=1):
            page = doc.new_page()
            where = fitz.Point(50, 50)
            page.insert_text(where, f"Page {i}", fontsize=24)
            where = fitz.Point(50, 100)
            page.insert_text(where, verse, fontsize=16)
        doc.save(pdf_file.name)
        doc.close()

        create_project_from_local_pdf_inner(
            pdf_path=pdf_file.name,
            display_title=display_title,
            app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            creator_id=user.id,
            task_status=LocalTaskStatus(),
        )

        project = session.scalars(select(db.Project).filter_by(slug=slug)).first()
        project.status = ProjectStatus.ACTIVE
        session.flush()

        stmt = select(db.PageStatus).filter_by(name="reviewed-0")
        unreviewed = session.scalars(stmt).one()

        for page, verse in zip(project.pages, BHAGAVAD_GITA_VERSES):
            content = f"<page><verse>{verse}</verse></page>"
            revision = db.Revision(
                project_id=project.id,
                page_id=page.id,
                author_id=user.id,
                status_id=unreviewed.id,
                content=content,
            )
            session.add(revision)

        session.commit()
        click.echo(f'Created toy project "{display_title}" with 10 pages.')


if __name__ == "__main__":
    cli()
