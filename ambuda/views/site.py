import functools
import json
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, url_for, abort
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.queries as q
from ambuda import xml


bp = Blueprint("site", __name__)


@bp.route("/")
def index():
    return render_template("index.html", texts=q.texts())


@bp.route("/about/")
def about():
    return render_template("about.html")


@bp.route("/contact/")
def contact():
    return render_template("contact.html")


@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500
