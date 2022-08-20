from flask import Blueprint, render_template


bp = Blueprint("about", __name__)


@bp.route("/")
def index():
    return render_template("about/index.html")


@bp.route("/mission")
def mission():
    return render_template("about/mission.html")


@bp.route("/values")
def values():
    return render_template("about/values.html")


@bp.route("/roadmap")
def roadmap():
    return render_template("about/roadmap.html")


@bp.route("/people")
def people():
    return render_template("about/people.html")


@bp.route("/code-and-data")
def code_and_data():
    return render_template("about/code-and-data.html")


@bp.route("/our-name")
def name():
    return render_template("about/our-name.html")


@bp.route("/contact")
def contact():
    return render_template("about/contact.html")

@bp.route("/privacy")
def privacy():
    return render_template("about/privacy.html")
