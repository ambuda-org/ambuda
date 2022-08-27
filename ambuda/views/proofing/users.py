from datetime import date, datetime, timedelta
from typing import Optional

from flask import (
    Blueprint,
    abort,
    flash,
    render_template,
    request,
)

from flask_wtf import FlaskForm
from wtforms import BooleanField, FormField

import ambuda.queries as q
from ambuda import database as db
from ambuda.utils.auth import admin_required


#: ISO weekday correspanding to Sunday.
ISO_SUNDAY = 7


bp = Blueprint("users", __name__)


class RolesForm(FlaskForm):
    pass


def _count_user_revisions_per_day(user_id: int) -> dict[datetime, int]:
    session = q.get_session()
    revisions = session.query(db.Revision).filter_by(author_id=user_id).all()

    counts = {}
    for r in sorted(revisions, key=lambda x: x.created):
        key = r.created.date()
        if key not in counts:
            counts[key] = 1
        else:
            counts[key] += 1
    return counts


def _get_heatmap_dates(last_date: Optional[date] = None):
    """Return a year's worth of dates up to and including `last_date`.

    We construct a year's worth of dates then backfill until the first date is
    on a Sunday.

    :param `last_date`: the last date to include.
    """
    last_date = last_date or datetime.now().date()

    # Round start date to nearest Sunday.
    first_date = last_date - timedelta(days=365)
    if first_date.isoweekday() != ISO_SUNDAY:
        first_date -= timedelta(days=first_date.isoweekday())

    num_days = (last_date - first_date).days
    return [first_date + timedelta(days=i) for i in range(num_days)]


@bp.route("/<username>/")
def user(username):
    user_ = q.user(username)
    if not user_:
        abort(404)

    revision_counts = _count_user_revisions_per_day(user_.id)

    dates_1y = _get_heatmap_dates()
    return render_template(
        "proofing/user.html",
        user=user_,
        dates_1y=dates_1y,
        revision_counts=revision_counts,
    )


@bp.route("/<username>/edits")
def user_edits(username):
    user_ = q.user(username)
    if not user_:
        abort(404)

    session = q.get_session()
    user_revisions = session.query(db.Revision).filter_by(author_id=user_.id).all()
    return render_template(
        "proofing/user-edits.html", user=user_, user_revisions=user_revisions
    )


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
def user_admin(username):
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
        "proofing/user-admin.html",
        user=user_,
        form=form,
    )
