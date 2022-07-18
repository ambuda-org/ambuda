from indic_transliteration import sanscript


def devanagari(s: str) -> str:
    """HK to Devanagari."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    """HK to Roman."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)
