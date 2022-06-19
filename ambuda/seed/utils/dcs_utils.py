"""Parse DCS data into a structured format."""

import re
from dataclasses import dataclass
from typing import Iterator

import conllu


@dataclass
class Token:
    form: str
    lemma: str
    parse: str


@dataclass
class Block:
    slug: str
    tokens: list[Token]


@dataclass
class Section:
    slug: str
    blocks: list[Block]


@dataclass
class FullParse:
    section_slug: str
    block_slug: str
    form: str
    lemma: str
    parse: str


FIELDS = [
    "id",
    "form",
    "lemma",
    "upos",
    "xpos",
    "tags",
    "unk_1",
    "unk_2",
    "unk_3",
    "unk_4",
    "dcs_id",
    "form_no_sandhi",
    "unk_5",
]


# https://github.com/OliverHellwig/sanskrit/blob/master/dcs/data/conllu/lookup/pos.csv
UPOS = {
    "CAD": "i",
    # 'CADA': 'UNK',
    "CADP": "i",
    "CCD": "i",
    "CCM": "i",
    "CEM": "i",
    "CGDA": "vi",
    "CGDI": "vi",
    # 'CIN': 'UNK',
    "CNG": "i",
    "CQT": "i",
    "CSB": "i",
    "CX": "i",
    "JJ": "a",
    "JQ": "n",
    "KDG": "va",
    "KDP": "va",
    "NC": "n",
    # 'NP': 'UNK',
    "NUM": "va",
    "PPP": "va",
    "PPR": "n",
    "PPX": "n",
    "PRC": "n",
    "PRD": "n",
    # 'PRF': 'UNK',
    "PRI": "n",
    "PRL": "n",
    "PRQ": "n",
    "V": "v",
}
PARSE = {
    "a": ["Gender", "Case", "Number"],
    "i": [],
    "n": ["Gender", "Case", "Number"],
    "p": ["Gender", "Case", "Number"],
    "va": ["Gender", "Case", "Number", "VerbForm"],
    "vi": [],
}
VALUES = {
    "Nom": "1",
    "Acc": "2",
    "Ins": "3",
    "Dat": "4",
    "Abl": "5",
    "Gen": "6",
    "Loc": "7",
    "Voc": "8",
    "Cpd": "c",
    "Masc": "m",
    "Fem": "f",
    "Neut": "n",
    "Sing": "s",
    "Dual": "d",
    "Plur": "p",
    "3": "3",
    "2": "2",
    "1": "1",
    "_": "_",
    "": "_",  # missing gender, e.g. for aham/tvam
    "Part": "part",
    "Gdv": "krtya",
}
TENSE_MOODS = {
    ("Aor", "Ind"): "lun",
    ("Aor", "Jus"): "lun_unaug",
    ("Aor", "Prec"): "ashirlin",
    ("Fut", "Cond"): "lrn",
    ("Fut", "Ind"): "lrt",
    ("Impf", "Ind"): "lan",
    ("Ind", "Ind"): "_",
    ("Perf", "Ind"): "lit",
    ("Pres", "Imp"): "lot",
    ("Pres", "Ind"): "lat",
    ("Pres", "Jus"): "lan_unaug",
    ("Pres", "Opt"): "vidhilin",
    ("Pres", "Sub"): "lot",
}


def parse_part_of_speech(upos):
    return UPOS[upos]


def parse_tags(pos, tags):
    data = {}
    for field in tags.split("|"):
        k, _, v = field.partition("=")
        data[k] = v

    buf = []
    if pos == "v":
        buf = [VALUES[data["Person"]], VALUES[data["Number"]]]
        tm = (data["Tense"], data["Mood"])
        buf.append(TENSE_MOODS[tm])
    else:
        for key in PARSE[pos]:
            value = data.get(key, "_")
            buf.append(VALUES[value])
    return "-".join(buf)


def is_multilemma(token):
    return isinstance(token["id"], tuple)


def parse_token(token) -> Token:
    form = token["form_no_sandhi"]
    if form == "_":
        form = token["form"]

    lemma = token["lemma"]
    pos = parse_part_of_speech(token["xpos"])
    tags = parse_tags(pos, token["tags"])
    return Token(form, lemma, pos + "-" + tags)


def parse_block(line) -> Block:
    return Block(
        slug=line.metadata["text_line_counter"],
        tokens=[parse_token(t) for t in line if not is_multilemma(t)],
    )


def parse_sections(text: str) -> list[Section]:
    data = {}
    section_slug = None
    lines = conllu.parse(text, fields=FIELDS)

    for i, line in enumerate(lines):
        if "# chapter" in line.metadata:
            if data:
                yield Section(slug=section_slug, blocks=list(data.values()))
                data = {}

            section_slug = line.metadata["# chapter"]
            continue

        assert section_slug
        block = parse_block(line)

        if block.slug not in data:
            data[block.slug] = block
        else:
            data[block.slug].tokens.extend(block.tokens)

    if data:
        yield Section(slug=section_slug, blocks=list(data.values()))


def get_parsed_rows(path) -> Iterator[FullParse]:
    with open(path) as f:
        text = f.read()

    # Make DCS metadata compatible with CONLLU.
    text = re.sub(r"# (\w+):", r"# \1 =", text)
    for section in parse_sections(text):
        for block in section.blocks:
            for token in block.tokens:
                yield FullParse(
                    section_slug=section.slug,
                    block_slug=block.slug,
                    form=token.form,
                    lemma=token.lemma,
                    parse=token.parse,
                )


if __name__ == "__main__":
    run()
