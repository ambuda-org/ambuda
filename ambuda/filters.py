"""Manages various small template filters."""

from datetime import datetime

from dateutil.relativedelta import relativedelta
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


def time_ago(dt: datetime) -> str:
    rd = relativedelta(datetime.utcnow(), dt)
    for name in ["months", "days", "hours", "minutes", "seconds"]:
        n = getattr(rd, name)
        if n:
            if n == 1:
                name = name[:-1]
            return f"{n} {name} ago"
    return "now"
