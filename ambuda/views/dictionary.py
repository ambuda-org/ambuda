from indic_transliteration import sanscript
from flask import jsonify
from flask import Blueprint

from ambuda import queries as Q
from ambuda import xml


api = Blueprint("api", __name__)


@api.route("/dict/<key>")
def ajax_entry(key):
    key = key.strip()
    slp1_key = sanscript.transliterate(key, sanscript.HK, sanscript.SLP1)
    rows = Q.select_mw(slp1_key)
    entries = [xml.transform_mw(r.value) for r in rows]
    return jsonify(entries=entries)
