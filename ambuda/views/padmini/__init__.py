"""View logic for Padmini, our Sanskrit search tool.


Core features
-------------

Padmini performs the following actions on each query:

1. Dictionary lookup. We check the raw query against the dictionaries in our
   database. This feature is similar to what is found in other dictionary
   tools.

2. Word analysis. We check the user's query against our rich lexicon of
   inflected Sanskrit words. If a match is found, we display the word with its
   morphological information.

3. Expression analysis. This is an extension of (2) that supports a stream of
   words as opposed to a single word entry. We distinguish this case from (2)
   because (3) might not always provide a single-word solution.


Our code
--------

This module accepts a raw query and creates a result set that we can display to
the user. Submodules, such as `expressions.py`, handle 


Future hopes
------------

In the future, we hope to provide:

- fuzzy search
- basic regex search
- dictionary lookup for non-Sanskrit words
- compound analysis
- dependency parsing
- meter recognition
- corpus search and frequency statistics
- text-to-speech
- translation
"""

import json

from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from indic_transliteration import detect, sanscript
from vidyut.cheda import Chedaka, Token

from ambuda import queries as q
from ambuda.views.api import bp as api
from ambuda.views.padmini import cheda
from ambuda.views.padmini import dictionaries
from ambuda.views.padmini import utils

bp = Blueprint("padmini", __name__)


@bp.route("/")
def index():
    """Index page with a basic search form."""
    return render_template("padmini/index.html")


@bp.route("/search/")
def search_with_no_query():
    """If the query is missing, just redirect to the index page."""
    return redirect(url_for("padmini.index"))


@bp.route("/search/<query>")
def search(query):
    """Results for some query."""

    input_encoding = detect.detect(query)
    slp1_query = utils.standardize_query(query, input_encoding=input_encoding)

    dict_sources = request.args.get("d", "").split(",")
    dict_results = dictionaries.create_results(slp1_query, dict_sources)
    has_any_dict_results = any(v for v in dict_results.values())

    if has_any_dict_results:
        cheda_results = []
    else:
        cheda_results = cheda.create_results(slp1_query)

    js_defaults = {
        "input_encoding": input_encoding,
        "query": query,
    }

    return render_template(
        "padmini/results-page.html",
        query=query,
        input_encoding=input_encoding,
        dict_results=dict_results,
        cheda_results=cheda_results,
        js_defaults=json.dumps(js_defaults),
    )
