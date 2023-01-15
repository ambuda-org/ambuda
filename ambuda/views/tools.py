"""Views for basic site pages."""

from flask import Blueprint, redirect, render_template, session, url_for

from ambuda import queries as q

bp = Blueprint("tools", __name__)


@bp.route("/cheda")
def cheda():
    return render_template("tools/cheda.html")
