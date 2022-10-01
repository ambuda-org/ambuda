from flask import Blueprint, abort, redirect, render_template, url_for
from indic_transliteration import detect, sanscript

import ambuda.queries as q
from ambuda.utils import xml
from ambuda.utils.dict_utils import expand_apte_keys, expand_skd_keys, standardize_key
from ambuda.views.api import bp as api

bp = Blueprint("dictionaries", __name__)


def _create_query_keys(sources: list[str], query: str) -> list[str]:
    query = query.strip()
    input_scheme = detect.detect(query)
    slp1_key = sanscript.transliterate(query, input_scheme, sanscript.SLP1)

    slp1_key = standardize_key(slp1_key)
    keys = [slp1_key]

    if any(x in sources for x in {"apte", "apte-sh"}):
        keys.extend(expand_apte_keys(slp1_key))
    if "shabdakalpadruma" in sources:
        keys.extend(expand_skd_keys(slp1_key))

    return keys


def _fetch_entries(sources: list[str], query: str) -> dict[str, str]:
    keys = _create_query_keys(sources, query)
    rows = q.dict_entries(sources, keys)

    dictionaries = q.dictionaries().values()
    dict_id_to_slug = {d.id: d.slug for d in dictionaries}

    transforms = {
        "apte": xml.transform_apte_sanskrit_english,
        "apte-sh": xml.transform_apte_sanskrit_hindi,
        "shabdartha-kaustubha": xml.transform_sak,
        "mw": xml.transform_mw,
        "vacaspatyam": xml.transform_vacaspatyam,
        "shabdakalpadruma": xml.transform_mw,
    }

    results = {d.slug: [] for d in dictionaries if d.slug in sources}
    for r in rows:
        slug = dict_id_to_slug[r.dictionary_id]
        fn = transforms.get(slug, xml.transform_mw)
        results[slug].append(fn(r.value))
    return results


@bp.route("/")
def index():
    """Show the dictionary lookup tool."""
    return render_template("dictionaries/index.html")


@bp.route("/<slug>/")
def version(slug):
    dictionaries = q.dictionaries()
    if slug not in dictionaries:
        abort(404)
    # TODO: set chosen dictionary as UX view
    return redirect(url_for("dictionaries.index"))


@bp.route("/<list:sources>/<query>")
def entry(sources, query):
    """Show a specific dictionary entry."""
    # Abort if sources aren't reasonable.
    if not sources:
        abort(404)
    dictionaries = q.dictionaries()
    for source in sources:
        if source not in dictionaries:
            abort(404)

    entries = _fetch_entries(sources, query)
    return render_template("dictionaries/index.html", query=query, entries=entries)


@api.route("/dictionaries/<list:sources>/<query>")
def entry_htmx(sources, query):
    dictionaries = q.dictionaries()
    # if source not in dictionaries:
    #    abort(404)

    entries = _fetch_entries(sources, query)
    return render_template("htmx/dictionary-results.html", query=query, entries=entries)
