#!/usr/bin/env python3

import getpass
from pathlib import Path

import click
from slugify import slugify
from sqlalchemy import or_

import ambuda
from ambuda import database as db
from ambuda import queries as q
from ambuda.tasks.projects import create_project_inner
from ambuda.tasks.utils import LocalTaskStatus


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

    session = q.get_session()
    existing_user = (
        session.query(db.User)
        .where(or_(db.User.username == username, db.User.email == email))
        .first()
    )
    if existing_user is not None:
        if existing_user.username == username:
            raise click.ClickException(f'User "{username}" already exists.')
        else:
            raise click.ClickException(f'Email "{email}" already exists.')

    new_user = db.User(username=username, email=email)
    new_user.set_password(raw_password)
    session.add(new_user)
    session.commit()


@cli.command()
@click.option("--username", help="the user to modify")
@click.option("--role", help="the role to add")
def add_role(username, role):
    """Add the given role to the given user.

    In particular, `add-role <user> admin` will give a user administrator
    privileges and grant them full access to Ambuda's data and content.
    """
    session = q.get_session()
    u = session.query(db.User).where(db.User.username == username).first()
    if u is None:
        raise click.ClickException(f'User "{username}" does not exist.')
    r = session.query(db.Role).where(db.Role.name == role).first()
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
        arbitrary_user = session.query(db.User).first()
        if not arbitrary_user:
            raise click.ClickException(
                "Every project must have a user that created it. "
                "But, no users were found in the database.\n"
                "Please create a user first with `create-user`."
            )

        slug = slugify(title)
        page_image_dir = (
            Path(current_app.config["UPLOAD_FOLDER"]) / "projects" / slug / "pages"
        )
        page_image_dir.mkdir(parents=True, exist_ok=True)
        create_project_inner(
            title=title,
            pdf_path=pdf_path,
            output_dir=str(page_image_dir),
            creator_id=arbitrary_user.id,
            task_status=LocalTaskStatus(),
        )


if __name__ == "__main__":
    cli()
