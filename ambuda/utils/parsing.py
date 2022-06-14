from dataclasses import dataclass


@dataclass
class Token:
    form: str
    lemma: str
    parse: str


POS = {
    "n": "noun",
    "a": "adjective",
    "v": "verb",
    "i": "indeclinable",
    "va": "participle",
    "vi": "verbal indeclinable",
}
GENDERS = {
    "m": "masculine",
    "f": "feminine",
    "n": "neuter",
    "_": "",
}
CASES = {
    "1": "nominative",
    "2": "accusative",
    "3": "instrumental",
    "4": "dative",
    "5": "ablative",
    "6": "genitive",
    "7": "locative",
    "8": "vocative",
    "c": "compounded",
}
PERSONS = {
    "3": "third-person",
    "2": "second-person",
    "1": "first-person",
}
NUMBERS = {
    "s": "singular",
    "d": "dual",
    "p": "plural",
    "_": "",
}
LAKARAS = {
    "lat": "present",
    "lit": "perfect",
    "lut": "periphrastic. future",
    "lrt": "simple future",
    "lot": "imperative",
    "lan": "imperfect",
    "vidhilin": "optative",
    "lun": "aorist",
    "lrn": "conditional",
}


def readable_parse(parse: str):
    """Make the parse readable to English readers."""
    pos, _, sub_parse = parse.partition("-")
    fields = sub_parse.split("-")

    if pos in ("n", "a"):
        gender, case_, number = fields
        gender = GENDERS[gender]
        case_ = CASES[case_]
        number = NUMBERS[number]
        sub_parse = f"{gender} {case_} {number}"
    elif pos == "v":
        person, number, lakara = fields
        person = PERSONS[person]
        number = NUMBERS[number]
        lakara = LAKARAS[lakara]
        sub_parse = f"{person} {number} {lakara}"
    elif pos == "i":
        pass
    elif pos == "v":
        person, number, la = fields
    elif pos == "i":
        sub_parse = None
    elif pos == "va":
        gender, case_, number, _ = fields
        gender = GENDERS[gender]
        case_ = CASES[case_]
        number = NUMBERS[number]
        sub_parse = f"{gender} {case_} {number}"

    part_of_speech = POS[pos]
    if sub_parse:
        return f"{part_of_speech}, {sub_parse}"
    else:
        return f"{part_of_speech}"


def render_blob(blob: str):
    """Make parse data human-readable.

    Parse data is currently just a TSV string. In time, we'll clean it up.
    But for now, just work with the blob."""
    rows = []
    for line in blob.splitlines():
        form, lemma, parse = line.split("\t")
        rows.append(Token(form, lemma, readable_parse(parse)))
    return rows
