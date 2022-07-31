"""Views related to texts: title pages, sections, verses, etc."""

from flask import Blueprint, render_template, abort
from indic_transliteration import sanscript
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.queries as q
from ambuda import xml
from ambuda.consts import TEXT_CATEGORIES
from ambuda.views.api import bp as api


bp = Blueprint("texts", __name__)

# A hacky list that decides which texts have parse data.
HAS_PARSE = {
    "ramayanam",
    "mahabharatam",
    "meghadutam-kale",
    "kiratarjuniyam",
    "kumarasambhavam",
    "saundaranandam",
    "kokilasandesha",
    "bodhicaryavatara",
}


def _prev_cur_next(sections: list[db.TextSection], slug: str):
    """Get the previous, current, and next esctions.

    :param sections: all of the sections in this text.
    :param slug: the slug for the current section.
    """
    found = False
    i = 0
    for i, s in enumerate(sections):
        if s.slug == slug:
            found = True
            break

    if not found:
        raise ValueError(f"Unknown slug {slug}")

    prev = sections[i - 1] if i > 0 else None
    cur = sections[i]
    next = sections[i + 1] if i < len(sections) - 1 else None
    return prev, cur, next


def _section_groups(sections: list[db.TextSection]):
    grouper = {}
    for s in sections:
        key, _, _ = s.slug.rpartition(".")
        if key not in grouper:
            grouper[key] = []
        grouper[key].append(s)
    return grouper


def _hk_to_dev(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


@bp.route("/")
def index():
    """Show all texts."""
    all_texts = {t.slug: t for t in q.texts()}
    return render_template(
        "texts/index.html", categories=TEXT_CATEGORIES, texts=all_texts
    )


@bp.route("/<slug>/")
def text(slug):
    """Show a text's title page and contents."""
    text = q.text(slug)
    if text is None:
        abort(404)

    section_groups = _section_groups(text.sections)
    return render_template("texts/text.html", text=text, section_groups=section_groups)


@bp.route("/<slug>/about")
def text_about(slug):
    """Show a text's metadata."""
    text = q.text(slug)
    if text is None:
        abort(404)

    header_data = xml.parse_tei_header(text.header)
    return render_template(
        "texts/text-about.html",
        text=text,
        header=header_data,
    )


@bp.route("/<slug>/resources")
def text_resources(slug):
    """Show a text's downloadable resources."""
    text = q.text(slug)
    if text is None:
        abort(404)

    return render_template("texts/text-resources.html", text=text)


@bp.route("/<text_slug>/<section_slug>")
def section(text_slug, section_slug):
    """Show a specific section of a text."""
    text = q.text(text_slug)
    if text is None:
        abort(404)

    try:
        prev, cur, next = _prev_cur_next(text.sections, section_slug)
    except ValueError:
        abort(404)

    # Single-section text should have only the slug 'all'.
    if not prev and not next:
        if section_slug != "all":
            abort(404)

    # Fetch with content blocks
    cur = q.text_section(text.id, section_slug)

    with q.get_session() as sess:
        blob = "<div>" + "".join(b.xml for b in cur.blocks) + "</div>"
        content = xml.transform_tei(blob)

    has_parse = text.slug in HAS_PARSE

    return render_template(
        "texts/section.html",
        text=text,
        prev=prev,
        section=cur,
        next=next,
        content=content,
        has_parse=has_parse,
    )


@api.route("/texts/<text_slug>/<section_slug>")
def section_htmx(text_slug, section_slug):
    text = q.text(text_slug)
    if text is None:
        abort(404)

    try:
        prev, cur, next = _prev_cur_next(text.sections, section_slug)
    except ValueError:
        abort(404)

    # Fetch with content blocks
    cur = q.text_section(text.id, section_slug)

    with q.get_session() as sess:
        blob = "<div>" + "".join(b.xml for b in cur.blocks) + "</div>"
        content = xml.transform_tei(blob)

    return render_template(
        "htmx/text-section.html",
        text=text,
        prev=prev,
        section=cur,
        next=next,
        content=content,
    )


@api.route("/texts/<text_slug>/blocks/<block_slug>")
def block_htmx(text_slug, block_slug):
    text = q.text(text_slug)
    if text is None:
        abort(404)

    block = q.block(text.id, block_slug)
    if not block:
        abort(404)

    content = xml.transform_tei(block.xml)
    return render_template(
        "htmx/text-block.html",
        content=content,
    )
