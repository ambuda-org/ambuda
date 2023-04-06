"""General information about Ambuda."""

from flask import Blueprint, render_template, redirect, url_for

from ambuda import queries as q

bp = Blueprint("about", __name__)

people = Blueprint("people", __name__)
bp.register_blueprint(people, url_prefix="/people")


@bp.route("/")
def index():
    return render_template("about/index.html")


@bp.route("/mission")
def mission():
    return render_template("about/mission.html")


@bp.route("/values")
def values():
    return render_template("about/values.html")


@people.route("/")
def index():
    return redirect(url_for("about.people.core"))


@people.route("/core")
def core():
    return render_template("about/people/core.html")


@people.route("/proofing")
def proofing():
    proofers = q.proofer_biographies()
    return render_template("about/people/proofing.html", proofers=proofers)


@bp.route("/code-and-data")
def code_and_data():
    return render_template("about/code-and-data.html")


@bp.route("/our-name")
def name():
    return render_template("about/our-name.html")


@bp.route("/contact")
def contact():
    return render_template("about/contact.html")


@bp.route("/terms")
def terms():
    return render_template("about/terms.html")


@bp.route("/privacy-policy")
def privacy():
    return render_template("about/privacy.html")
