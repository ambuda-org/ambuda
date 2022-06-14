from indic_transliteration import detect, sanscript
from flask import abort, jsonify, redirect, render_template, url_for
from flask import Blueprint

import ambuda.queries as q
from ambuda import xml
from ambuda.dict_utils import standardize_key, expand_apte_keys
from ambuda.views.api import bp as api


bp = Blueprint("dictionaries", __name__)


def _fetch_entries(version, query):
    query = query.strip()
    input_scheme = detect.detect(query)

    slp1_key = sanscript.transliterate(query, input_scheme, sanscript.SLP1)
    slp1_key = standardize_key(slp1_key)
    if version == "apte":
        keys = expand_apte_keys(slp1_key)
        rows = q.dict_entries(version, keys)
    else:
        rows = q.dict_entry(version, slp1_key)

    transforms = {
        "apte": xml.transform_apte,
        "mw": xml.transform_mw,
        "vacaspatyam": xml.transform_vacaspatyam,
        "shabdakalpadruma": xml.transform_mw,
    }
    fn = transforms.get(version, xml.transform_mw)
    return [fn(r.value) for r in rows]


@api.route("/dict/<version>/<query>")
def ajax_entry(version, query):
    dictionaries = q.dictionaries()
    if version not in dictionaries:
        abort(404)

    entries = _fetch_entries(version, query)
    return jsonify(entries=entries)


@bp.route("/")
def index():
    return render_template("dictionaries/index.html")


@bp.route("/<slug>/")
def version(slug):
    dictionaries = q.dictionaries()
    if slug not in dictionaries:
        abort(404)
    # TODO: set chosen dictionary as UX view
    return redirect(url_for("dictionaries.index"))


@bp.route("/<version>/<query>")
def entry(version, query):
    dictionaries = q.dictionaries()
    if version not in dictionaries:
        abort(404)

    entries = _fetch_entries(version, query)
    return render_template("dictionaries/index.html", entries=entries)
