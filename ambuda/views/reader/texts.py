"""Views related to texts: title pages, sections, verses, etc."""

import json
import logging

import ambuda.database as db
import ambuda.queries as q

#from ambuda.consts import TEXT_CATEGORIES
from ambuda.utils import xml
from ambuda.utils.json_serde import AmbudaJSONEncoder
from ambuda.views.api import bp as api
from ambuda.views.reader.schema import Block, Section
from flask import Blueprint, abort, jsonify, render_template, url_for
from indic_transliteration import sanscript

bp = Blueprint("texts", __name__)
LOG = logging.getLogger(__name__)

# A hacky list that decides which texts have parse data.
HAS_NO_PARSE = {
    "raghuvamsham",
    "bhattikavyam",
    "shatakatrayam",
    "shishupalavadham",
    "shivopanishat",
    "catuhshloki",
}

#: A special slug for single-section texts.
#:
#: Some texts are small enough that they don't have any divisions (sargas,
#: kandas). For simplicity, we represent such texts as having one section that
#: we just call "all." All such texts are called *single-section texts.*
SINGLE_SECTION_SLUG = "all"


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


def _make_section_url(text: db.Text, section: db.TextSection | None) -> str | None:
    if section:
        return url_for("texts.section", text_slug=text.slug, section_slug=section.slug)
    else:
        return None


def _section_groups(sections: list[db.TextSection]) -> dict[str, list[db.TextSection]]:
    """Groups section hierarchically according to their slug.

    For example, the sections `[1.1, 1.2, 2.1, 2.2]` will be grouped as::

        { "1": [1.1, 1.2], "2": [2.1, 2.2] }
    """
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

    # Initialize a dictionary with keys as genres and values as texts in those genres
    text_genres = {}

    # Retrieve all genres from the database
    genres = q.genres()

    # Iterate over each genre and retrieve texts in that genre
    for genre in genres:
        texts = q.texts_genre(genre=genre)
        text_genres[genre.name.lower()] = texts
    return render_template(
        "texts/index.html", categories=text_genres, texts=all_texts
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
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)

    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    is_single_section_text = not prev and not next_
    if is_single_section_text:
        # Single-section texts have exactly one section whose slug should be
        # `SINGLE_SECTION_SLUG`. If the slug is anything else, abort.
        if section_slug != SINGLE_SECTION_SLUG:
            abort(404)

    has_no_parse = text_.slug in HAS_NO_PARSE

    # Fetch with content blocks
    cur = q.text_section(text_.id, section_slug)

    with q.get_session() as _:
        _ = cur.blocks

    blocks = []
    for block in cur.blocks:
        blocks.append(
            Block(
                slug=block.slug,
                mula=xml.transform_text_block(block.xml),
            )
        )

    data = Section(
        text_title=_hk_to_dev(text_.title),
        section_title=_hk_to_dev(cur.title),
        blocks=blocks,
        prev_url=_make_section_url(text_, prev),
        next_url=_make_section_url(text_, next_),
    )
    json_payload = json.dumps(data, cls=AmbudaJSONEncoder)

    return render_template(
        "texts/section.html",
        text=text_,
        prev=prev,
        section=cur,
        next=next_,
        json_payload=json_payload,
        html_blocks=data.blocks,
        has_no_parse=has_no_parse,
        is_single_section_text=is_single_section_text,
    )


@api.route("/texts/<text_slug>/blocks/<block_slug>")
def block_htmx(text_slug, block_slug):
    text = q.text(text_slug)
    if text is None:
        abort(404)

    block = q.block(text.id, block_slug)
    if not block:
        abort(404)

    html_block = xml.transform_text_block(block.xml)
    return render_template(
        "htmx/text-block.html",
        slug=block.slug,
        html=html_block,
    )


@api.route("/texts/<text_slug>/<section_slug>")
def reader_json(text_slug, section_slug):
    # NOTE: currently unused, since we bootstrap from a JSON blob in the
    # original request.
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)

    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    with q.get_session() as _:
        html_blocks = [xml.transform_text_block(b.xml) for b in cur.blocks]

    data = Section(
        text_title=_hk_to_dev(text_.title),
        section_title=_hk_to_dev(cur.title),
        blocks=html_blocks,
        prev_url=_make_section_url(text, prev),
        next_url=_make_section_url(text, next_),
    )
    return jsonify(data)
