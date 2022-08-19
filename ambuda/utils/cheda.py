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
    "n": {"en": "noun", "sa": "subantam"},
    "a": {"en": "adjective", "sa": "visheShaNam"},
    "v": {"en": "verb", "sa": "ti~Nantam"},
    "i": {"en": "indeclinable", "sa": "avyayam"},
    "va": {"en": "participle", "sa": "kRRidantam"},
    "vi": {"en": "verbal indeclinable", "sa": "avyayam"},
}
GENDERS = {
    "m": {"en": "masculine", "sa": "puṃliṅga"},
    "f": {"en": "feminine", "sa": "strīliṅga"},
    "n": {"en": "neuter", "sa": "napuṃsakaliṅga"},
    "": {"en": "", "sa": ""},
}
CASES = {
    "1": {"en": "nominative", "sa": "prathamA"},
    "2": {"en": "accusative", "sa": "dvitIyA"},
    "3": {"en": "instrumental", "sa": "tRRitIyA"},
    "4": {"en": "dative", "sa": "caturthI"},
    "5": {"en": "ablative", "sa": "pa~nchamI"},
    "6": {"en": "genitive", "sa": "ShaShThI"},
    "7": {"en": "locative", "sa": "saptamI"},
    "8": {"en": "vocative", "sa": "sambodhanam"},
    "c": {"en": "compounded", "sa": "samAsa"},
}
PERSONS = {
    "3": {"en": "third-person", "sa": "prathama"},
    "2": {"en": "second-person", "sa": "madhyama"},
    "1": {"en": "first-person", "sa": "uttama"},
}
NUMBERS = {
    "s": {"en": "singular", "sa": "ekavacanam"},
    "d": {"en": "dual", "sa": "dvivacanam"},
    "p": {"en": "plural", "sa": "bahuvacanam"},
    "": {"en": "", "sa": ""},
}
LAKARAS = {
    "lat": {"en": "present", "sa": "laT (vartamAna)"},
    "lit": {"en": "perfect", "sa": "liT (parokShabhUta)"},
    "lut": {"en": "periphrastic future", "sa": "luT (anadyatana)"},
    "lrt": {"en": "simple future", "sa": "lRRit (bhaviShyan)"},
    "lot": {"en": "imperative", "sa": "loT (Aj~nA)"},
    "lan": {"en": "imperfect", "sa": "la~N (anadyatanabhUta)"},
    "vidhilin": {"en": "optative", "sa": "vidhili~N"},
    "lun": {"en": "aorist", "sa": "lu~N (bhUta)"},
    "lun_unaug": {"en": "aorist (unaugmented)", "sa": "lu~N (bhUta)"},
    "lrn": {"en": "conditional", "sa": "lRRi~N (saMketa)"},
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
