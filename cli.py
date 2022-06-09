#!/usr/bin/env python3

import click
from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.seed.common import create_db


engine = create_db()


@click.group()
def cli():
    pass


@cli.command()
@click.argument("slug")
def delete_text(slug: str):
    with Session(engine) as session:
        text = session.query(db.Text).where(db.Text.slug == slug).first()
        if text:
            session.delete(text)
            session.commit()


if __name__ == "__main__":
    cli()
