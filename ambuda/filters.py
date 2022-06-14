from indic_transliteration import sanscript
from markupsafe import Markup


def devanagari(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)


def slp2dev(s: str) -> str:
    # TODO: actually use devanagari. For now, no sanscript, so use IAST so that
    # everyone can read it.
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.IAST)


def sa_roman(s: str) -> str:
    result = roman(s)
    return f'<span lang="sa">{result}</span>'
