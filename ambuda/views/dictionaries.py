import functools

from flask import Blueprint, abort, redirect, render_template, url_for
from indic_transliteration import detect, sanscript

import ambuda.queries as q
from ambuda.utils import xml
from ambuda.utils.dict_utils import expand_apte_keys, expand_skd_keys, standardize_key
from ambuda.views.api import bp as api

bp = Blueprint("dictionaries", __name__)


@functools.cache
def _get_dictionary_data() -> dict[str, str]:
    return {d.slug: d.title for d in q.dictionaries()}


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
    entries = q.dict_entries(sources, keys)

    transforms = {
        "apte": xml.transform_apte_sanskrit_english,
        "apte-sh": xml.transform_apte_sanskrit_hindi,
        "shabdartha-kaustubha": xml.transform_sak,
        "mw": xml.transform_mw,
        "vacaspatyam": xml.transform_vacaspatyam,
        "shabdakalpadruma": xml.transform_mw,
    }

    results = {}
    for source_slug, source_entries in entries.items():
        fn = transforms.get(source_slug, xml.transform_mw)
        html_blobs = [fn(e.value) for e in source_entries]
        results[source_slug] = html_blobs
    return results


@bp.route("/")
def index():
    """Show the dictionary lookup tool."""
    dictionaries = _get_dictionary_data()
    return render_template("dictionaries/index.html", dictionaries=dictionaries)


@bp.route("/<list:slugs>/")
def sources(slugs):
    if not all(s in _get_dictionary_data() for s in slugs):
        abort(404)
    # TODO: set chosen dictionaries as UX view
    return redirect(url_for("dictionaries.index"))


@bp.route("/<list:sources>/<query>")
def entry(sources, query):
    """Show a specific dictionary entry."""
    dictionaries = _get_dictionary_data()
    if not sources or not all(s in dictionaries for s in sources):
        # Abort if sources aren't reasonable.
        abort(404)

    entries = _fetch_entries(sources, query)
    return render_template(
        "dictionaries/index.html",
        query=query,
        entries=entries,
        dictionaries=dictionaries,
    )


@api.route("/dictionaries/<list:sources>/<query>")
def entry_htmx(sources, query):
    dictionaries = _get_dictionary_data()
    if not sources or not all(s in _get_dictionary_data() for s in sources):
        # Abort if sources aren't reasonable.
        abort(404)

    entries = _fetch_entries(sources, query)
    return render_template(
        "htmx/dictionary-results.html",
        query=query,
        entries=entries,
        dictionaries=dictionaries,
    )
