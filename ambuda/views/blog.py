"""Various endpoints for the Ambuda blog.

The blog is a work in progress and doesn't have a defined voice, level of
formality, etc. For now, we use it for any text content that it doesn't make
sense to check into version control.
"""

from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user
from flask_wtf import FlaskForm
from slugify import slugify
from wtforms import StringField
from wtforms.validators import DataRequired
from wtforms.widgets import TextArea

from ambuda import database as db
from ambuda import queries as q
from ambuda.utils.auth import admin_required

bp = Blueprint("blog", __name__)


class CreatePostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])


class EditPostForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    slug = StringField("Slug", validators=[DataRequired()])
    content = StringField("Content", widget=TextArea(), validators=[DataRequired()])


class DeletePostForm(FlaskForm):
    slug = StringField("Slug", validators=[DataRequired()])


@bp.route("/")
def index():
    """List of all posts."""
    posts = q.blog_posts()
    return render_template("blog/index.html", posts=posts)


@bp.route("/p/<slug>")
def post(slug):
    """A single post."""
    post = q.blog_post(slug)
    if post is None:
        abort(404)

    return render_template("blog/post.html", post=post)


@bp.route("/create", methods=["GET", "POST"])
@admin_required
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

        flash("Created post.")
        return redirect(url_for("blog.index"))

    return render_template("blog/create-post.html", form=form)


@bp.route("/p/<slug>/edit", methods=["GET", "POST"])
@admin_required
def edit_post(slug):
    """Edit an existing post."""
    post_ = q.blog_post(slug)
    if post_ is None:
        abort(404)

    form = EditPostForm(obj=post_)
    if form.validate_on_submit():
        session = q.get_session()
        form.populate_obj(post_)
        session.commit()

        flash("Edited post.")
        return redirect(url_for("blog.index"))

    return render_template("blog/edit-post.html", post=post_, form=form)


@bp.route("/p/<slug>/delete", methods=["GET", "POST"])
@admin_required
def delete_post(slug):
    """Edit an existing post."""
    post_ = q.blog_post(slug)
    if post_ is None:
        abort(404)

    form = DeletePostForm()
    if form.validate_on_submit():
        if form.slug.data == slug:
            session = q.get_session()
            session.delete(post_)
            session.commit()

            flash(f"Deleted post {slug}")
            return redirect(url_for("blog.index"))
        else:
            form.slug.errors.append("Mismatch with project slug.")

    return render_template("blog/delete-post.html", post=post_, form=form)
