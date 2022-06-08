from sqlalchemy.orm import Session

from ambuda import database as db
from ambuda.seed.common import create_db


engine = create_db()


def delete_text(slug: str):
    with Session(engine) as session:
        text = session.query(db.Text).where(db.Text.slug == slug).first()
        if text:
            session.delete(text)
            session.commit()

