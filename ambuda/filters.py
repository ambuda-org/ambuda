from indic_transliteration import sanscript


def devanagari(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)


def sa_roman(s: str) -> str:
    result = roman(s)
    return f'<span lang="sa">{result}</span>'
