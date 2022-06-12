from indic_transliteration import detect, sanscript
from flask import jsonify, render_template
from flask import Blueprint

import ambuda.queries as q
from ambuda import xml
from ambuda.dict_utils import standardize_key, expand_apte_keys


api = Blueprint("api", __name__)
bp = Blueprint("dictionaries", __name__)


def _fetch_entries(version, query):
    query = query.strip()
    input_scheme = detect.detect(query)

    slp1_key = sanscript.transliterate(query, input_scheme, sanscript.SLP1)
    slp1_key = standardize_key(slp1_key)
    if version == "apte":
        keys = expand_apte_keys(slp1_key)
        rows = q.dict_entries(version, keys)
        entries = [xml.transform_apte(r.value) for r in rows]
    else:
        rows = q.dict_entry(version, slp1_key)
        if version == "vacaspatyam":
            entries = [xml.transform_vacaspatyam(r.value) for r in rows]
        else:
            entries = [xml.transform_mw(r.value) for r in rows]
    return entries


@api.route("/dict/<version>/<query>")
def ajax_entry(version, query):
    entries = _fetch_entries(version, query)
    return jsonify(entries=entries)


@bp.route("/")
def index():
    return render_template("dictionaries/index.html")


@bp.route("/<version>/<query>")
def entry(version, query):
    entries = _fetch_entries(version, query)
    return render_template("dictionaries/index.html", entries=entries)
