"""Dictionary routes and API.

A *source* is our term for a specific dictionary source, e.g. the Apte
Sanskrit-English dictionary from 1890. To support lookup against multiple
dictionaries, our code here generally works with *lists* of sources.

A source list is valid iff all of the following conditions are met:
- the list is non-empty.
- at least one source in the list exists in the dictionary.

If a source list is invalid, we raise a 404 error.
"""


import functools
from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for
from indic_transliteration import detect, sanscript

import ambuda.queries as q
from ambuda.utils import xml
from ambuda.utils.dict_utils import expand_apte_keys, expand_skd_keys, standardize_key
from ambuda.views.api import bp as api

bp = Blueprint("dictionaries", __name__)


@functools.cache
def _get_dictionary_data() -> dict[str, str]:
    """A lazy singleton for dictionary data."""
    return {d.slug: d.title for d in q.dictionaries()}


def _create_query_keys(sources: list[str], query: str) -> list[str]:
    """Expands the given `query` according to the orthographic conventions of
    different dictionaries.

    Examples:
    - `deva` to `devaH` for Apte and others
    - `saMBU` to `samBU` for Monier-Williams and others
    """
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


def fetch_entries(sources: list[str], query: str) -> dict[str, str]:
    keys = _create_query_keys(sources, query)
    entries = q.dict_entries(sources, keys)

    transforms = {
        "apte": xml.transform_apte_sanskrit_english,
        "apte-sh": xml.transform_apte_sanskrit_hindi,
        "shabdartha-kaustubha": xml.transform_sak,
        "mw": xml.transform_mw,
        "vacaspatyam": xml.transform_vacaspatyam,
        "amara": xml.transform_amarakosha,
        "shabdakalpadruma": xml.transform_mw,
    }

    results = {}
    for source_slug, source_entries in entries.items():
        fn = transforms.get(source_slug, xml.transform_mw)
        html_blobs = [fn(e.value) for e in source_entries]
        results[source_slug] = html_blobs
    return results


def _handle_form_submission(
    url_sources: list[str] = None, url_query: Optional[str] = None
):
    """Handle a search request defined with query parameters.

    If a user with JavaScript disabled clicks the Search button, the user's query
    will be encoded as URL parameters. Some examples:

    - https://ambuda.org/tools/dictionaries?source=mw&q=deva
    - https://ambuda.org/tools/dictionaries/apte/svarga?source=mw&q=deva

    This function makes a reasonable effort to rewrite such URLs into a
    standard form:

        https://ambuda.org/tools/dictionaries/mw/deva

    :param sources: sources already encoded in the URL
    :param url_query: query already encoded in the URL
    """
    sources = url_sources
    query = url_query

    if request.args:
        source = request.args.get("source")
        if source:
            sources = [source]
        query = request.args.get("q", query)
    if sources and query:
        return redirect(url_for("dictionaries.entry", sources=sources, query=query))
    else:
        return redirect(url_for("dictionaries.index"))


def create_results(slp1_query: str, sources: list[str]):
    sources = request.args.get("d", "").split(",")
    return fetch_entries(sources, slp1_query)
