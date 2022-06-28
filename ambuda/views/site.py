"""Views for basic site pages."""

from flask import Blueprint, render_template


bp = Blueprint("site", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/contact/")
def contact():
    return render_template("contact.html")


@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500
