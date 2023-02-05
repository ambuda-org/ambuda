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

import functools
import json

from flask import Blueprint, render_template, jsonify, request
from indic_transliteration import detect, sanscript
from vidyut.cheda import Chedaka, Token

from ambuda import queries as q
from ambuda.views.api import bp as api
from ambuda.views.padmini import dictionaries as dicts
from ambuda.views.padmini import utils

bp = Blueprint("padmini", __name__)


@functools.cache
def chedaka():
    """A lazy singleton for our word splitter."""
    return Chedaka("/Users/akp/projects/vidyut/vidyut-cheda/data/vidyut-0.2.0")


@bp.route("/")
def index():
    """Index page with a basic search form."""
    return render_template("padmini/index.html")


@bp.route("/search/<query>")
def search(query):
    """Results for some query."""

    input_encoding = detect.detect(query)
    slp1_query = utils.standardize_query(query, input_encoding=input_encoding)

    dict_results = dicts.fetch_entries(["mw"], query)
    js_defaults = {
        "input_encoding": input_encoding,
        "query": query,
    }
    return render_template(
        "padmini/results-page.html",
        query=query,
        input_encoding=input_encoding,
        dict_results=dict_results,
        js_defaults=json.dumps(js_defaults),
    )


def handle_query(q):
    """Handle the user's query and create a result set."""
    # Lemma -- use query as dictionary headword
    # Word -- check for word in kosha
    # Cheda -- run padaccheda
    try:
        tokens = chedaka.run(slp1_query)
    except Exception:
        # TODO: For now, use an exhaustive exception guard. As `vidyut`
        # matures, see if we can avoid most or all exceptions here.
        tokens = []

    _standardize_tokens(tokens)
    return render_template("htmx/cheda.html", tokens=tokens)
