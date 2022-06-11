"""Utils for serving and generating dictionary data."""

import re


def standardize_key(s: str) -> str:
    buf = list(s)
    # Always apply parasavaraNatva.
    for m in re.finditer("(M)(.)", s):
        anusvara_index = m.span(1)[0]
        consonant = m.group(2)

        res = "M"
        if consonant in "kKgGN":
            res = "N"
        if consonant in "cCjJY":
            res = "Y"
        if consonant in "wWqQR":
            res = "R"
        if consonant in "tTdDn":
            res = "n"
        if consonant in "pPbBm":
            res = "m"
        buf[anusvara_index] = res
    return "".join(buf)


def standardize_apte_key(s: str) -> str:
    """Standardize Apte's conventions against the other dictionaries.

    Apte uses aH and aM to compactly encode the gender of -a stems.
    For those who don't know this convention, it can be difficult
    to look up a word. So, standardize by removing H/M from the end
    of nominal stems.
    """
    apte_endings = ("aH", "aM", "iH", "uH", "UH")
    if any(s.endswith(x) for x in apte_endings):
        return s[:-1]
    else:
        return s
