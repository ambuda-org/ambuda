from flask import Blueprint, render_template, abort

import ambuda.queries as q
from ambuda.utils import parsing as parse_utils
from ambuda.views.api import bp as api


bp = Blueprint("parses", __name__)


@bp.route("<text_slug>/<block_slug>")
def block(text_slug, block_slug):
    text = q.text_meta(text_slug)
    if text is None:
        abort(404)

    block = q.block_meta(text.id, block_slug)
    if block is None:
        abort(404)

    parse = q.block_parse(block.id)
    if parse is None:
        abort(404)

    return render_template(
        "texts/block-parse.html", tokens=parse_utils.render_blob(parse.data)
    )


@api.route("/parses/<text_slug>/<block_slug>")
def block_htmx(text_slug, block_slug):
    text = q.text_meta(text_slug)
    if text is None:
        abort(404)

    block = q.block_meta(text.id, block_slug)
    if block is None:
        abort(404)

    parse = q.block_parse(block.id)
    if parse:
        tokens = parse_utils.render_blob(parse.data)
    else:
        tokens = []

    return render_template("htmx/parsed-tokens.html", tokens=tokens)
