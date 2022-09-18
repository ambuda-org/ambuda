"""General information about Ambuda."""

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from slugify import slugify
from wtforms import StringField
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q
from ambuda.views.proofing.decorators import moderator_required

bp = Blueprint("blog", __name__)


class CreatePostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])


class EditPostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])


@bp.route("/")
def index():
    """List of all posts."""
    posts = q.blog_posts()
    return render_template("blog/index.html", posts=posts)


@bp.route("/create", methods=["GET", "POST"])
@moderator_required
def create_post():
    """Create a new post."""
    form = CreatePostForm()
    if form.validate_on_submit():
        title = form.title.data
        slug = slugify(title)
        content = form.content.data

        post = db.BlogPost(
            title=title,
            slug=slug,
            content=content,
            author_id=current_user.id,
        )
        session = q.get_session()
        session.add(post)
        session.commit()
        return redirect(url_for("blog.index"))

    return render_template("blog/create-post.html", form=form)


@bp.route("/p/<slug>")
def post(slug):
    """A single post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)

    return render_template("blog/post.html", post=post)


@bp.route("/p/<slug>/edit")
def edit_post(slug, methods=["GET", "POST"]):
    """Edit an existing post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)

    form = EditPostForm()
    if form.validate_on_submit():
        return "OK"

    return render_template("blog/edit-post.html", form=form)


@bp.route("/p/<slug>/delete")
def delete_post(slug, methods=["GET", "POST"]):
    """Edit an existing post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)

    form = EditPostForm()
    if form.validate_on_submit():
        return "OK"

    return render_template("blog/edit-post.html", form=form)
