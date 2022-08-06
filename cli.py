#!/usr/bin/env python3

import click
import getpass
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ambuda import database as db
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
                raise click.ClickException(f"User {username} already exists.")
            else:
                raise click.ClickException(f"Email {email} already exists.")

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
            raise click.ClickException(f"User {username} does not exist.")
        r = session.query(db.Role).where(db.Role.name == role).first()
        if r is None:
            raise click.ClickException(f"Role {role} is not defined.")
        if r in u.roles:
            raise click.ClickException(f"User {username} already has role {role}.")

        u.roles.append(r)
        session.add(u)
        session.commit()


if __name__ == "__main__":
    cli()
