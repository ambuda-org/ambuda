from flask import (
    Blueprint,
    abort,
    render_template,
)
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea

import ambuda.queries as q
from ambuda import database as db

bp = Blueprint("tagging", __name__)


class EditBlockForm(FlaskForm):
    version = HiddenField("Page version")
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])


@bp.route("/")
def index():
    texts = q.texts()
    return render_template("tagging/index.html", texts=texts)


@bp.route("/<slug>/")
def text(slug):
    text_ = q.text(slug)
    if text_ is None:
        abort(404)

    session = q.get_session()
    num_blocks = session.query(db.TextBlock).filter_by(text_id=text_.id).count()
    num_parsed_blocks = session.query(db.BlockParse).filter_by(text_id=text_.id).count()
    return render_template(
        "tagging/text.html",
        text=text_,
        num_blocks=num_blocks,
        num_parsed_blocks=num_parsed_blocks,
    )


@bp.route("/<text_slug>/<section_slug>/")
def section(text_slug, section_slug):
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)

    # Find the current section.
    cur = None
    for section in text_.sections:
        if section.slug == section_slug:
            cur = section
            break
    if cur is None:
        abort(404)

    form = EditBlockForm()
    return render_template("tagging/section.html", text=text_, section=cur, form=form)


@bp.route("/<text_slug>/blocks/<block_slug>")
def edit_block(text_slug, block_slug):
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)

    block = q.block(text_.id, block_slug)
    if block is None:
        abort(404)

    block_parse = q.block_parse(block.id)
    if block_parse is None:
        abort(404)

    form = EditBlockForm()
    return render_template(
        "tagging/edit-block.html", text=text_, block=block, parse=block_parse, form=form
    )


@bp.route("/<text_slug>/<block_slug>", methods=["POST"])
@login_required
def edit_block_post(text_slug, block_slug):
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)

    form = EditBlockForm()
    return render_template("tagging/edit-block.html", text=text_, form=form)
