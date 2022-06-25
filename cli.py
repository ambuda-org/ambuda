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
def list_dicts():
    """List dictionaries in the database."""
    with Session(engine) as session:
        dicts = session.query(db.Dictionary).all()
    for d in dicts:
        print(d.slug)


@cli.command()
@click.argument("slug")
def delete_dict(slug: str):
    """Delete the given dictionary."""
    with Session(engine) as session:
        d = session.query(db.Dictionary).where(db.Dictionary.slug == slug).first()
        if d:
            session.delete(d)
            session.commit()


@cli.command()
def list_texts():
    """List texts in the database."""
    with Session(engine) as session:
        texts = session.query(db.Text).all()
    for t in texts:
        print(t.slug)


@cli.command()
@click.argument("slug")
def delete_text(slug: str):
    """Delete the given text."""
    with Session(engine) as session:
        text = session.query(db.Text).where(db.Text.slug == slug).first()
        if text:
            session.delete(text)
            session.commit()


if __name__ == "__main__":
    cli()
