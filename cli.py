#!/usr/bin/env python3

import click
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.seed.utils.itihasa_utils import create_db


engine = create_db()


@click.group()
def cli():
    pass


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
