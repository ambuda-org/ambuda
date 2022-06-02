from indic_transliteration import sanscript


def devanagari(s: str) -> str:
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)
