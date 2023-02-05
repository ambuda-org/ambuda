"""Handles Padmiin"""

from indic_transliteration import detect, sanscript
from vidyut.cheda import Token


def standardize_query(q: str) -> str:
    """Standardize the given query and convert it to SLP1.

    :param s: the input query in an arbitrary encoding scheme.
    """
    q = q.strip()
    input_encoding = detect.detect(q)
    return sanscript.transliterate(q, input_encoding, "slp1")
