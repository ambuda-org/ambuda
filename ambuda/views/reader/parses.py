from flask import Blueprint, render_template, abort

import ambuda.queries as q
from ambuda.utils import word_parses as parse_utils
from ambuda.utils.parse_alignment import align_text_with_parse
from ambuda.views.api import bp as api


bp = Blueprint("parses", __name__)


@bp.route("/<text_slug>/<block_slug>")
def block(text_slug, block_slug):
    """Show the analysis for a specific block."""
    text = q.text_meta(text_slug)
    if text is None:
        abort(404)

    block = q.block(text.id, block_slug)
    if block is None:
        abort(404)

    parse = q.block_parse(block.id)
    if parse is None:
        abort(404)

    tokens = parse_utils.extract_tokens(parse.data)
    aligned = align_text_with_parse(block.xml, tokens)
    return render_template("texts/block-parse.html", aligned=aligned)


@api.route("/parses/<text_slug>/<block_slug>")
def block_parse_htmx(text_slug, block_slug):
    text = q.text_meta(text_slug)
    if text is None:
        abort(404)

    block = q.block(text.id, block_slug)
    if block is None:
        abort(404)

    parse = q.block_parse(block.id)
    if not parse:
        abort(404)

    tokens = parse_utils.extract_tokens(parse.data)
    aligned = align_text_with_parse(block.xml, tokens)
    return render_template(
        "htmx/parsed-tokens.html",
        text_slug=text_slug,
        block_slug=block_slug,
        aligned=aligned,
    )
