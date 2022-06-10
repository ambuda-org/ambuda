from indic_transliteration import detect, sanscript
from flask import jsonify, render_template
from flask import Blueprint

import ambuda.queries as q
from ambuda import xml


api = Blueprint("api", __name__)
bp = Blueprint("dictionaries", __name__)


@api.route("/dict/<version>/<key>")
def ajax_entry(version, key):
    key = key.strip()
    input_scheme = detect.detect(key)
    slp1_key = sanscript.transliterate(key, input_scheme, sanscript.SLP1)

    rows = q.select_mw(version, slp1_key)
    entries = [xml.transform_mw(r.value) for r in rows]
    return jsonify(entries=entries)


@bp.route("/")
def index():
    return render_template("dictionaries/index.html")
