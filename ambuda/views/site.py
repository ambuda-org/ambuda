import functools
import json
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, url_for
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.queries as q
from ambuda import xml

bp = Blueprint("site", __name__)


def _prev_cur_next(sections: list[db.TextSection], slug: str):
    found = True
    for i, s in enumerate(sections):
        if s.slug == slug:
            found = True
            break

    if not found:
        raise Exception(f"Unknown slug {slug}")

    prev = sections[i - 1] if i > 0 else None
    cur = sections[i]
    next = sections[i + 1] if i < len(sections) + 1 else None
    return prev, cur, next


def _section_groups(sections):
    grouper = {}
    for s in sections:
        key, _, _ = s.slug.rpartition(".")
        if key not in grouper:
            grouper[key] = []
        grouper[key].append(s)
    return grouper


@bp.route("/")
def index():
    return render_template("index.html", texts=q.texts())


@bp.route("/texts/<slug>/")
def text(slug):
    text = q.text(slug)
    section_groups = _section_groups(text.sections)
    return render_template("text.html", text=text, section_groups=section_groups)


@bp.route("/texts/<text>/<path>/")
def section(text, path):
    text = q.text(text)
    prev, cur, next = _prev_cur_next(text.sections, path)

    with Session(q.engine) as sess:
        content = xml.transform_tei(cur.xml)

    return render_template(
        "section.html",
        text=text,
        prev=prev,
        section=cur,
        next=next,
        section_groups=_section_groups(text.sections),
        content=content,
    )
