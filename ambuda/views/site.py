"""Views for basic site pages."""

from flask import Blueprint, redirect, render_template, session, url_for

from ambuda.consts import LOCALES
from ambuda import queries as q

bp = Blueprint("site", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/contact")
def contact():
    return redirect(url_for("about.contact"))


@bp.route("/donate")
def donate():
    return render_template("donate.html")


@bp.route("/support")
def support():
    return render_template("support.html")


@bp.route("/test-sentry-500")
def sentry_500():
    """Sentry integration test. Should trigger a 500 error in prod."""
    _ = 1 / 0


@bp.app_errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@bp.app_errorhandler(413)
def request_too_large(e):
    return render_template("413.html"), 413


@bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


@bp.route("/language/<slug>")
def set_language(slug=None):
    locale = [L for L in LOCALES if slug == L.slug]
    if locale:
        locale = locale[0]
        session["locale"] = locale.code
    return redirect(url_for("site.index"))
