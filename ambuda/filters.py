from indic_transliteration import sanscript
from markupsafe import Markup


def devanagari(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)


def slp2dev(s: str) -> str:
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def sa_roman(s: str) -> str:
    result = roman(s)
    return f'<span lang="sa">{result}</span>'
