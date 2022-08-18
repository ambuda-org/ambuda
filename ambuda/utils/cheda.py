"""Utilities for working with parse data.

This module is quite sloppy and will likely change in the future.
"""

from dataclasses import dataclass


@dataclass
class Token:
    """Represents a parsed word."""

    form: str
    lemma: str
    raw_parse: str
    en_parse: str
    is_compounded: bool


POS = {
    "n": {"en": "noun", "sa": "subanta"},
    "a": {"en": "adjective", "sa": "viśeṣaṇa"},
    "v": {"en": "verb", "sa": "tiṅanta"},
    "i": {"en": "indeclinable", "sa": "avyaya"},
    "va": {"en": "participle", "sa": "participle"},
    "vi": {"en": "verbal indeclinable", "sa": "avyaya"},
}
GENDERS = {
    "m": {"en": "masculine", "sa": "puṃliṅga"},
    "f": {"en": "feminine", "sa": "strīliṅga"},
    "n": {"en": "neuter", "sa": "napuṃsakaliṅga"},
    "": {"en": "", "sa": ""},
}
CASES = {
    "1": {"en": "nominative", "sa": "prathamā vibhakti"},
    "2": {"en": "accusative", "sa": "dvitīyā vibhakti"},
    "3": {"en": "instrumental", "sa": "tṛtīyā vibhakti"},
    "4": {"en": "dative", "sa": "caturthī vibhakti"},
    "5": {"en": "ablative", "sa": "pañcamī vibhakti"},
    "6": {"en": "genitive", "sa": "ṣaṣṭhī vibhakti"},
    "7": {"en": "locative", "sa": "saptamī vibhakti"},
    "8": {"en": "vocative", "sa": "saṃbodhana vibhakti"},
    "c": {"en": "compounded", "sa": "samāsa"},
}
PERSONS = {
    "3": {"en": "third-person", "sa": "prathama puruṣa"},
    "2": {"en": "second-person", "sa": "madhyama puruṣa"},
    "1": {"en": "first-person", "sa": "uttama puruṣa"},
}
NUMBERS = {
    "s": {"en": "singular", "sa": "ekavacana"},
    "d": {"en": "dual", "sa": "dvivacana"},
    "p": {"en": "plural", "sa": "bahuvacana"},
    "": {"en": "", "sa": ""},
}
LAKARAS = {
    "lat": {"en": "present", "sa": "laṭ"},
    "lit": {"en": "perfect", "sa": "liṭ"},
    "lut": {"en": "periphrastic future", "sa": "luṭ"},
    "lrt": {"en": "simple future", "sa": "lṛt"},
    "lot": {"en": "imperative", "sa": "loṭ"},
    "lan": {"en": "imperfect", "sa": "laṅ"},
    "vidhilin": {"en": "optative", "sa": "vidhiliṅ"},
    "lun": {"en": "aorist", "sa": "luṅ"},
    "lun_unaug": {"en": "aorist (unaugmented)", "sa": "luṅ"},
    "lrn": {"en": "conditional", "sa": "lṛṅ"},
}


def readable_parse(parse: str, lang: str = "sa") -> str:
    """Make the parse readable to English readers."""
    fields = {}
    for field in parse.split(","):
        k, v = field.split("=")
        fields[k] = v

    pos = fields["pos"]
    sub_parse = None

    if pos in ("n", "a", "va"):
        try:
            gender, case_, number = fields["g"], fields["c"], fields["n"]
            gender = GENDERS[gender][lang]
            case_ = CASES[case_][lang]
            number = NUMBERS[number][lang]
            sub_parse = f"{gender} {case_} {number}"
        except KeyError:
            assert "comp" in fields
            sub_parse = "compounded"

    elif pos == "v":
        person, number, lakara = fields["p"], fields["n"], fields["l"]
        person = PERSONS[person][lang]
        number = NUMBERS[number][lang]
        lakara = LAKARAS[lakara][lang]
        sub_parse = f"{person} {number} {lakara}"
    elif pos in ("i", "vi"):
        pass

    part_of_speech = POS[pos][lang]
    if sub_parse:
        return f"{part_of_speech}, {sub_parse}"
    else:
        return f"{part_of_speech}"


def extract_tokens(blob: str) -> list[Token]:
    """Make parse data human-readable.

    Parse data is currently just a TSV string. In time, we'll clean it up.
    But for now, just work with the blob."""
    rows = []
    for line in blob.splitlines():
        form, lemma, parse = line.split("\t")
        human_parse = readable_parse(parse)
        token = Token(
            form,
            lemma,
            raw_parse=parse,
            en_parse=human_parse,
            is_compounded="compounded" in human_parse,
        )
        rows.append(token)
    return rows
