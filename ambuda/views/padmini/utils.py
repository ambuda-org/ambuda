"""Handles Padmiin"""

from indic_transliteration import detect, sanscript
from vidyut.cheda import Token


def standardize_query(q: str, input_encoding: str) -> str:
    """Standardize the given query and convert it to SLP1.

    :param q: the input query
    :param input_encoding: the input encoding for the query
    """
    q = q.strip()
    return sanscript.transliterate(q, input_encoding, "slp1")
