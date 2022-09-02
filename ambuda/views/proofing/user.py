from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    url_for,
)

from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import orm
from wtforms import BooleanField
from wtforms import StringField
from wtforms.widgets import TextArea

import ambuda.queries as q
from ambuda import database as db
from ambuda.utils.auth import admin_required
from ambuda.utils import heatmap


bp = Blueprint("user", __name__)


class RolesForm(FlaskForm):
    pass


class EditProfileForm(FlaskForm):
    description = StringField("Profile description", widget=TextArea())


@bp.route("/<username>/")
def summary(username):
    user_ = q.user(username)
    if not user_:
        abort(404)

    return render_template(
        "proofing/user/summary.html",
        user=user_,
    )


@bp.route("/<username>/activity")
def activity(username):
    """Summarize the user's public activity on Ambuda."""
    user_ = q.user(username)
    if not user_:
        abort(404)

    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision)
        .options(orm.defer(db.Revision.content))
        .filter_by(author_id=user_.id)
        .order_by(db.Revision.created.desc())
        .all()
    )
    recent_projects = (
        session.query(db.Project)
        .filter_by(creator_id=user_.id)
        .order_by(db.Project.created_at.desc())
        .all()
    )

    recent_activity = [("revision", r.created, r) for r in recent_revisions]
    recent_activity += [("project", p.created_at, p) for p in recent_projects]
    hm = heatmap.create(x[1].date() for x in recent_activity)

    return render_template(
        "proofing/user/activity.html",
        user=user_,
        recent_activity=recent_activity,
        heatmap=hm,
    )


@bp.route("/<username>/edit", methods=["GET", "POST"])
@login_required
def edit(username):
    """Allow a user to edit their own information."""
    user_ = q.user(username)
    if not user_:
        abort(404)

    # Only this user can edit their bio.
    if username != current_user.username:
        abort(403)

    form = EditProfileForm(obj=user_)
    if form.validate_on_submit():
        session = q.get_session()
        form.populate_obj(user_)
        session.commit()
        flash("Saved changes.", "success")
        return redirect(url_for("proofing.user.summary", username=username))

    return render_template("proofing/user/edit.html", user=user_, form=form)


def _make_role_form(roles, user_):
    descriptions = {
        "p1": "Proofreading 1 (can make pages yellow)",
        "p2": "Proofreading 2 (can make pages green)",
    }
    # We're mutating a global object, but this is safe because we're doing so
    # in an idempotent way.
    for r in roles:
        attr_name = f"id_{r.id}"
        user_has_role = r in user_.roles
        setattr(
            RolesForm,
            attr_name,
            BooleanField(descriptions.get(r.name, r.name), default=user_has_role),
        )
    return RolesForm()


@bp.route("/<username>/admin", methods=["GET", "POST"])
@admin_required
def admin(username):
    """Adjust a user's roles."""
    user_ = q.user(username)
    if not user_:
        abort(404)

    session = q.get_session()
    # Exclude admin.
    # (Admin roles should be added manually by the server administrator.)
    all_roles = [r for r in session.query(db.Role).all() if r.name != "admin"]
    all_roles = sorted(all_roles, key=lambda x: x.name)

    form = _make_role_form(all_roles, user_)

    if form.validate_on_submit():
        id_to_role = {r.id: r for r in all_roles}
        user_role_ids = {r.id for r in user_.roles}
        for key, should_have_role in form.data.items():
            if not key.startswith("id_"):
                continue

            _, _, id = key.partition("_")
            id = int(id)
            role_ = id_to_role[id]
            has_role = role_.id in user_role_ids
            if has_role and not should_have_role:
                user_.roles.remove(role_)
            if not has_role and should_have_role:
                user_.roles.append(role_)

        session.add(user_)
        session.commit()

        flash("Saved changes.", "success")

    return render_template(
        "proofing/user/admin.html",
        user=user_,
        form=form,
    )
