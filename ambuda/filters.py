"""Manages various small template filters."""

from indic_transliteration import sanscript


def slp_to_devanagari(s: str) -> str:
    """SLP1 to Devanagari."""
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def devanagari(s: str) -> str:
    """HK to Devanagari."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    """HK to Roman."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)
