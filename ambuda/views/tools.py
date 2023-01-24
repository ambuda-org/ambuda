"""Views for basic site pages."""

from indic_transliteration import detect, sanscript

from flask import Blueprint, render_template, jsonify, request
from vidyut import Chedaka

from ambuda import queries as q
from ambuda.views.api import bp as api

bp = Blueprint("tools", __name__)

c = Chedaka("/Users/akp/projects/vidyut/vidyut-cheda/data/vidyut-0.1.0")


@bp.route("/cheda")
def cheda():
    return render_template("tools/cheda.html")


@api.route("/vidyut/cheda", methods=["POST"])
def api_vidyut_cheda():
    data = request.json
    input_ = data.get("input") or ""

    encoding = detect.detect(input_)
    input_slp1 = sanscript.transliterate(input_, encoding, "slp1")
    tokens = c.tokenize(input_slp1)
    data = []
    for t in tokens:
        if t.text.endswith("s"):
            t.text = t.text[:-1] + "H"

    return render_template("htmx/cheda.html", tokens=tokens)
