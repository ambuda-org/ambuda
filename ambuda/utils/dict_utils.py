"""Utils for serving and generating dictionary data."""

import re


def standardize_key(s: str) -> str:
    """Standardize the dictionary lookup key.

    Different dictionary authors follow different conventions when writing Sanskrit
    words. This function standardizes these conventions so that users have a better
    lookup experience.

    Right now, the only standardization we apply is to convert an anusvāra followed
    by a consonant to its appropriate parasavarṇa ("similar to the following") sound.

    For examples, see the unit tests.

    :param s: the key to standardize.
    :return: a standardize key
    """
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


def expand_apte_keys(key: str) -> list[str]:
    """Expand a "standard" dict key when searching Apte.

    Apte uses aH and aM to compactly encode the gender of -a stems. For those
    who don't know this convention, it can be difficult to look up a word. So,
    expand the search space by generating extra search keys.
    """
    keys = [key]
    if key[-1] == "a":
        keys.append(key + "H")
        keys.append(key + "M")
    elif key[-1] in "AiIuUfFxXeEoO":
        keys.append(key + "H")
    if key[-1] == "m":
        keys.append(key[:-1] + "M")
    return keys


def expand_skd_keys(key: str) -> list[str]:
    """Expand a "standard" dict key when searching the Shabdakalpadruma.

    The Shabdakalpadruma generally states nominal stems in their prathamA-
    ekavacana (case 1 singular) form. Allow stem-based lookup by expanding
    search terms and speculatively generating pra-ek forms for each stem.
    """
    keys = [key]

    # Vowels
    if key[-1] == "a":
        # puṁliṅga
        keys.append(key + "H")
        # napuṁsakaliṅga
        keys.append(key + "M")
    elif key[-1] in "AiIuUfFxXeEoO":
        # puṁliṅga
        keys.append(key + "H")

    # Consonants
    elif key.endswith("an"):
        # puṁliṅga & napuṁsakaliṅga
        keys.append(key[:-2] + "A")
        keys.append(key[:-2] + "a")
    elif key.endswith("in"):
        # puṁliṅga & napuṁsakaliṅga
        keys.append(key[:-2] + "I")
        keys.append(key[:-2] + "i")
    else:
        prefix, last = key[:-1], key[-1]
        if last in "kKgG":
            keys.append(prefix + "k")
        elif last in "cCjJS":
            # vAc -> vAk
            # dfS -> dfk
            keys.append(prefix + "k")
            if last in "jJS":
                # rAj -> rAT
                # For more, see Ashtadhyayi 8.2.36
                keys.append(prefix + "w")
        elif last in "tTdD":
            # samiD -> samit
            keys.append(prefix + "t")
        elif last in "pPbB":
            # kakuB -> kakup
            keys.append(prefix + "p")
        elif last in "sr":
            keys.append(prefix + "H")
    return keys
