#!/usr/bin/env python3

import click
import getpass
from slugify import slugify
from sqlalchemy import or_
from sqlalchemy.orm import Session

import ambuda
from ambuda import database as db
from ambuda import queries as q
from ambuda.seed.utils.itihasa_utils import create_db


engine = create_db()


@click.group()
def cli():
    pass


@cli.command()
def create_user():
    """Add the given role to the given user."""
    username = input("Username: ")
    raw_password = getpass.getpass("Password: ")
    email = input("Email: ")

    with Session(engine) as session:
        u = (
            session.query(db.User)
            .where(or_(db.User.username == username, db.User.email == email))
            .first()
        )
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
@click.argument("username")
@click.argument("role")
def add_role(username: str, role: str):
    """Add the given role to the given user."""
    with Session(engine) as session:
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
@click.argument("title")
def create_test_project(title):
    """Create a test proofing project with 100 pages."""
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
        q.create_project(title=title, slug=slug, creator_id=arbitrary_user.id)
        project = q.project(slug)

        default_status = session.query(db.PageStatus).filter_by(name="reviewed-0").one()
        for i in range(1, 101):
            page = db.Page(
                project_id=project.id,
                slug=str(i),
                order=i,
                status_id=default_status.id,
            )
            session.add(page)
        session.commit()
    print(f'Created project "{title}" with slug "{slug}".')


if __name__ == "__main__":
    cli()
