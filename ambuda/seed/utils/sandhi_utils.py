"""An adhoc implementation of samAsa-sandhi.

We use this when extracting compound data from the Apte (1890) dictionary.
"""

# Sound groups defined in the Shiva Sutras.
AC = "aAiIuUfFxXeoEO"
HASH = "hyvrlYmNRnJBGQDjbgqd"
NAM = "YmRRn"
KHAR = "KPCWTcwtkpSzs"
ASH = AC + HASH

# No need for eEo support yet.
YAN = dict(zip("iIuUffxXO", ["y", "y", "v", "v", "r", "r", "l", "l", "Av"]))
GUNA_VRDDHI = dict(
    zip(["ai", "au", "af", "ax", "ae", "ao"], ["e", "o", "ar", "al", "E", "O"])
)

# 8.3.48
KASKADI = {
    "kas",
    "kOtas",
    "sadyas",
    "sAdyas",
    "sarpis",
    "Danus",
    "bahis",
    "yajus",
    "ayas",
    "tamas",
    "medas",
    "BAs",
    "ahar",
}


def _ac_sandhi(first, second) -> str:
    f = first[-1]
    s = second[0]
    # Similar
    if f.lower() == s.lower():
        return first[:-1] + f.upper() + second[1:]
    else:
        # guna-vrddhi
        if f in "aA":
            combo = f.lower() + s.lower()
            return first[:-1] + GUNA_VRDDHI[combo] + second[1:]
        elif f == "e":
            assert first == "Are"
            return first + second
        # iko yan aci
        else:
            return first[:-1] + YAN[f] + second


def _visarga_sandhi(first: str, second: str) -> str:
    # Won't appear in compounds
    assert first[-1] in "sr"

    s = second[0]
    if first.endswith("as"):
        if s == "a":
            return first[:-2] + "o" + second[1:]
        if s in HASH:
            return first[:-2] + "o" + second

    prefix = first[:-1]
    if s in "kK":
        # Encoding bug
        if (first, second) == ("aDas", "kzaM"):
            return "aDokzam"

        if first in KASKADI:
            if first[-2] in "aA":
                return prefix + "s" + second
            # e.g. bahizkfta
            else:
                return prefix + "z" + second
    if s in "cC":
        return prefix + "S" + second
    if s in "wW":
        return prefix + "z" + second
    if s in "tT":
        return prefix + "s" + second
    if s in ASH:
        return prefix + "r" + second
    return prefix + "H" + second


def _reduce_final_consonant(s: str) -> str:
    """s and r handled elsewhere."""
    f = s[-1]
    if s == "anaquh":
        return "anaqut"
    if f in "kKgG":
        f = "k"
    elif f in "cCjJS":
        f = "k"
    elif f in "wWqQz":
        f = "w"
    elif f in "tTdD":
        f = "t"
    elif f in "pPbB":
        f = "p"
    return s[:-1] + f


def _hal_sandhi(first, second) -> str:
    first = _reduce_final_consonant(first)
    f = first[-1]
    s = second[0]

    ac = {"k": "g", "w": "q", "t": "d", "p": "b", "N": "N", "m": "m"}
    _hash = ac.copy()
    _hash["m"] = "M"
    nasals = {
        "k": "N",
        "w": "R",
        "t": "N",
        "p": "m",
        "m": "M",
    }
    combos = {
        "kh": "gG",
        "th": "dD",
        "ph": "bB",
        "tS": "cC",
    }

    if f + s in combos:
        return first[:-1] + combos[f + s] + second[1:]
    if s in NAM:
        return first[:-1] + nasals[f] + second
    if s in HASH:
        return first[:-1] + _hash[f] + second
    if s in AC:
        return first[:-1] + ac[f] + second
    return first + second


def apply(first: str, second: str) -> str:
    if first[-1] == "n":
        if first == "ahan":
            first = "ahar"
        else:
            first = first[:-1]

    f = first[-1]
    s = second[0]
    if f in AC and s in AC:
        return _ac_sandhi(first, second)
    elif f in "sr":
        return _visarga_sandhi(first, second)
    elif f not in AC:
        return _hal_sandhi(first, second)
    else:
        return first + second
