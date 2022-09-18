"""General information about Ambuda."""

from flask import Blueprint, abort, render_template
from flask_login import current_user
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    """List of all posts."""
    posts = q.blog_posts()
    return render_template("blog/index.html", posts=posts)


@bp.route("/<slug>")
def post(slug):
    """A single post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)
    return render_template("blog/post.html", post=post)


@bp.route("/create", methods=["GET", "POST"])
def create_post():
    """Create a new post."""
    return render_template("blog/create.html")


@bp.route("/edit/<slug>")
def edit_post(slug, methods=["GET", "POST"]):
    """Edit an existing post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)

    return render_template("blog/edit.html")
