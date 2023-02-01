"""Handles Padmiin"""

from vidyut.cheda import Token


def standardize_query(q: str) -> str:
    """Standardize the given query and convert it to SLP1.

    :param s: the input query in an arbitrary encoding scheme.
    """
    encoding = detect.detect(q)
    return sanscript.transliterate(q, encoding, "slp1")
