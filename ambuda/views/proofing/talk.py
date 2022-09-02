from flask import Blueprint, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from wtforms import StringField
from wtforms.validators import DataRequired, Length
from wtforms.widgets import TextArea

from ambuda import queries as q

bp = Blueprint("talk", __name__)


class CreateThreadForm(FlaskForm):
    title = StringField("Title")
    content = StringField(
        "Message", widget=TextArea(), validators=[DataRequired(), Length(max=10000)]
    )


class CreatePostForm(FlaskForm):
    content = StringField(
        "Message", widget=TextArea(), validators=[DataRequired(), Length(max=10000)]
    )


class EditPostForm(FlaskForm):
    content = StringField(
        "Message", widget=TextArea(), validators=[DataRequired(), Length(max=10000)]
    )


@bp.route("/<slug>/talk/")
def board(slug):
    """Show all threads for some board."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    return render_template(
        "proofing/talk/board.html", project=project_, board=project_.board
    )


@bp.route("/<slug>/talk/create-thread", methods=["GET", "POST"])
@login_required
def create_thread(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = CreateThreadForm()
    if form.validate_on_submit():
        q.create_thread(
            board_id=project_.board_id,
            user_id=current_user.id,
            title=form.title.data,
            content=form.content.data,
        )
        return redirect(url_for("proofing.talk.board", slug=slug))

    return render_template(
        "proofing/talk/create-thread.html", project=project_, form=form
    )


@bp.route("/<project_slug>/talk/<thread_id>")
def thread(project_slug, thread_id):
    """Show all posts for some thread."""
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)

    thread = q.thread(id=thread_id)
    if thread is None:
        abort(404)

    return render_template("proofing/talk/thread.html", project=project_, thread=thread)


@bp.route("/<project_slug>/talk/<thread_id>/create", methods=["GET", "POST"])
@login_required
def create_post(project_slug, thread_id):
    """Create a post on an existing thread."""
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)

    thread_ = q.thread(id=thread_id)
    if thread_ is None or thread_.board_id != project_.board_id:
        abort(404)

    form = CreatePostForm()
    if form.validate_on_submit():
        q.create_post(
            board_id=project_.board_id,
            thread=thread_,
            user_id=current_user.id,
            content=form.content.data,
        )
        return redirect(
            url_for(
                "proofing.talk.thread",
                project_slug=project_.slug,
                thread_id=thread_.id,
            )
        )

    return render_template(
        "proofing/talk/create-post.html", project=project_, thread=thread_, form=form
    )


@bp.route("/<project_slug>/talk/<thread_id>/<post_id>/edit", methods=["GET", "POST"])
@login_required
def edit_post(project_slug, thread_id, post_id):
    """Edit an existing post."""
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)

    thread_ = q.thread(id=thread_id)
    if thread_ is None or thread_.board_id != project_.board_id:
        abort(404)

    post_ = q.post(id=post_id)
    if post_ is None or post_.thread_id != thread_.id:
        abort(404)

    if post_.author_id != current_user.id:
        abort(403)

    form = EditPostForm()
    if form.validate_on_submit():
        session = q.get_session()
        post_.update_content(form.content.data)
        session.add(post_)
        session.commit()
        return redirect(
            url_for(
                "proofing.talk.thread", project_slug=project_slug, thread_id=thread_id
            )
        )

    form.content.data = post_.content
    return render_template(
        "proofing/talk/edit-post.html",
        project=project_,
        thread=thread_,
        post=post_,
        form=form,
    )
