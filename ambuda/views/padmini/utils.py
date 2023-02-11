"""Handles Padmiin"""

import re

from indic_transliteration import detect, sanscript
from vidyut.cheda import Token


def standardize_query(query: str, input_encoding: str) -> str:
    """Standardize the given query and convert it to SLP1.

    :param q: the input query
    :param input_encoding: the input encoding for the query
    """
    query = query.strip()
    # Remove invisible characters (soft hyphens, etc.)
    query = "".join(c for c in query if c.isprintable())
    # Convert to SLP1 since our downstream libraries expect it.
    query = sanscript.transliterate(query, input_encoding, "slp1")
    return query
