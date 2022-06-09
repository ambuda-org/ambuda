from dataclasses import dataclass
from xml.etree import ElementTree as ET
from typing import Optional

from indic_transliteration import sanscript


@dataclass
class Rule:
    tag: Optional[str]
    attrib: dict[str, str]
    text_before: str
    text_after: str


def text(before="", after=""):
    return Rule(None, {}, before, after)


def elem(name: str, attrs=None, before="", after=""):
    return Rule(name, attrs or {}, before, after)


tei_transforms = {
    "div": elem("section"),
    "seg": elem("span"),
    "hi": text(),
    "note": None,
    "orig": elem("span"),
    "lg": elem("p", {"class": "x-verse"}),
    "l": elem("span", {"class": "x-pada"}),
    "section": elem("section"),
}

paren_rule = Rule("span", {"class": "paren"}, "(", ")")
bracket_rule = Rule("span", {"class": "paren"}, "[", "]")

# Tag meanings are documented here:
# https://www.sanskrit-lexicon.uni-koeln.de/talkMay2008/mwtags.html
mw_transforms = {
    # Root elements
    "H1": None,
    "H1A": None,
    "H1B": None,
    "H1E": None,
    "H2": None,
    "H2A": None,
    "H2B": None,
    "H3": None,
    "H3A": None,
    "H3B": None,
    "H4": None,
    "H4A": None,
    "H4B": None,
    # Record structure
    "h": None,
    "body": elem("li", {"class": "mw-entry"}),
    "tail": None,
    # Head information -- hide all of it.
    "hc1": None,
    "hc3": None,
    "key1": None,
    "key2": None,
    # Body -- special characters
    "b": bracket_rule,
    "b1": bracket_rule,
    "p": paren_rule,
    "p1": paren_rule,
    "quote": elem("q"),
    "sr": text("\u00b0"),
    "sr1": text("\u00b0"),
    "abE": None,
    "srs": text(""),
    "srs1": text(""),
    "shc": None,
    "shortlong": None,
    "auml": text("ä"),
    "euml": text("ë"),
    "ouml": text("ö"),
    "uuml": text("ü"),
    "etc": text("&c"),
    "etc1": text("&c"),
    "etcetc": text("&c"),
    "amp": text("&"),
    "eq": elem("abbr", None, before="="),
    "fs": text("/"),
    "msc": text(";"),
    "ccom": None,
    "ab": elem("abbr"),
    "etym": elem("i"),
    "s": elem("span", {"lang": "sa"}, "##", "##"),
    "ns": elem("span"),
    "s1": elem("span"),
    "bio": elem("b"),
    "bot": elem("b"),
    "root": text("\u221a"),
    "ls": elem("cite"),
    "lex": elem("span", {"class": "lex"}),
    "vlex": elem("span", {"class": "lex"}),
    "hom": None,
    "info": None,
    "lang": elem("span"),
    "lb": elem("br"),
    # Also distinct tail pc, should be treated differently
    "pc": None,
    "pcol": elem("span"),
    "cf": elem("abbr", before="cf."),
    "qv": elem("abbr", before="q.v."),
    "see": text(" see "),
    # Tail elements
    "L": None,
    "MW": None,
    "mul": None,
    "mat": None,
    "mscverb": None,
}


def transform_tei(blob: str) -> str:
    root = ET.fromstring(blob)

    for elem in root.iter():
        rule = tei_transforms[elem.tag]
        if rule is None:
            elem.tag = elem.text = None
            elem.clear()
            continue

        elem.tag = rule.tag
        elem.attrib = rule.attrib
        elem.text = "##" + (elem.text or "") + "##"

    untrans = ET.tostring(root, encoding="utf-8").decode("utf-8")
    return sanscript.transliterate(
        "##" + untrans, sanscript.HK, sanscript.DEVANAGARI, togglers={"##"}
    )


def transform_mw(blob: str) -> str:
    root = ET.fromstring(blob)

    for elem in root.iter():
        try:
            rule = mw_transforms[elem.tag]
        except KeyError:
            print(f"unknown key: {elem.tag}")
            continue
        if rule is None:
            elem.tag = elem.text = None
            continue

        elem.tag = rule.tag
        elem.attrib = rule.attrib or {}

        if rule.text_before:
            elem.text = rule.text_before + (elem.text or "")
        if rule.text_after:
            # No children: append after current text
            if len(elem) == 0:
                elem.text = (elem.text or "") + rule.text_after
            # Has children: append after last child
            else:
                last_child = elem[-1]
                last_child.tail = (last_child.tail or "") + rule.text_after

    untrans = ET.tostring(root, encoding="utf-8").decode("utf-8")
    return sanscript.transliterate(
        "##" + untrans, sanscript.SLP1, sanscript.IAST, togglers={"##"}
    )
