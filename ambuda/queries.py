from sqlalchemy import create_engine
from sqlalchemy.sql import *

import ambuda.database as db


def select_mw(key: str):
    engine = create_engine(db.DATABASE_URI)

    q = select([db.entries]).where(db.entries.c.key == key)
    with engine.connect() as conn:
        return conn.execute(q).fetchall()
