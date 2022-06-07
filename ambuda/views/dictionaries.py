from indic_transliteration import sanscript
from flask import jsonify, render_template
from flask import Blueprint

import ambuda.queries as q
from ambuda import xml


api = Blueprint("api", __name__)
bp = Blueprint("dictionaries", __name__)


@api.route("/dict/<key>")
def ajax_entry(key):
    key = key.strip()
    slp1_key = sanscript.transliterate(key, sanscript.HK, sanscript.SLP1)
    rows = q.select_mw("mw", slp1_key)
    entries = [xml.transform_mw(r.value) for r in rows]
    return jsonify(entries=entries)


@bp.route("/")
def index():
    return render_template("dictionaries/index.html")
