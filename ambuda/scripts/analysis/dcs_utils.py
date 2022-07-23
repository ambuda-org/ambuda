"""Parse DCS data into a structured format.

One term of art I use here: a "chunk" is a space-separated segment in the text.
"""

import re
from dataclasses import dataclass
from typing import Iterator

import conllu
from indic_transliteration import sanscript


@dataclass
class Token:
    """A token with parse data."""

    form: str
    lemma: str
    parse: str


@dataclass
class Phrase:
    """A group of tokens, usually corresponding to a half-verse."""

    raw: str
    slug: str
    tokens: list[Token]


@dataclass
class Section:
    """A group of phrases, usually a sarga."""

    slug: str
    phrases: list[Phrase]


# The DCS CONLLU fields in order.
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
    # Alternative if "form" == "_", but often differs from the underlying form.
    # e.g. underlying "avAptavAn" vs "avAptaH" here.
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
    "NUM": "n",
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


class POS:
    # tinanta
    VERB = "v"
    #: avyaya
    INDECLINABLE = "i"
    #: subanta, stem has a fixed gender
    NOUN = "n"
    #: subanta, stem has no fixed gender
    ADJECTIVE = "a"
    #: subanta, usually a sarvanAma
    PRONOUN = "p"

    #: kta-pratyaya, usually a participle
    VERBAL_ADJECTIVE = "va"
    #: usually -tum or -tvA
    VERBAL_INDECLINABLE = "vi"


# Map the DCS data into a scheme I prefer.
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
    "_": "",
    "": "",  # missing gender, e.g. for aham/tvam
    "Part": "part",
    "Gdv": "krtya",
}

# Maps Western tense/mood combinations to Paninian categories, which better
# describe later Sanskrit.
TENSE_MOODS = {
    ("Aor", "Ind"): "lun",
    ("Aor", "Imp"): "lun_imp",
    ("Aor", "Jus"): "lun_unaug",
    ("Aor", "Prec"): "ashirlin",
    ("Fut", "Cond"): "lrn",
    ("Fut", "Ind"): "lrt",
    ("Impf", "Ind"): "lan",
    # ("Ind", "Ind"): "",
    ("Perf", "Ind"): "lit",
    ("Perf", "Sub"): "lit_subj",
    ("Pres", "Imp"): "lot",
    ("Pres", "Ind"): "lat",
    ("Pres", "Jus"): "lan_unaug",
    ("Pres", "Opt"): "vidhilin",
    ("Pres", "Sub"): "lot",
}


def parse_part_of_speech(upos):
    """Map a UPOS speech tag into a more familiar category."""
    return UPOS[upos]


def create_parse_string(pos: str, tags: str) -> str:
    # Reshape raw field into dictionary
    data = {}
    for field in tags.split("|"):
        k, _, v = field.partition("=")
        data[k] = v

    # Translate into a minimal parse
    fields = {"pos": pos}
    if pos == POS.VERB:
        tm = (data["Tense"], data["Mood"])
        la = TENSE_MOODS[tm]
        fields.update(
            {
                "p": VALUES[data["Person"]],
                "n": VALUES[data["Number"]],
                "l": la,
            }
        )
    elif pos in {POS.NOUN, POS.ADJECTIVE, POS.PRONOUN}:
        try:
            fields.update(
                {
                    "g": VALUES[data["Gender"]],
                    "c": VALUES[data["Case"]],
                    "n": VALUES[data["Number"]],
                }
            )
        except KeyError:
            assert data["Case"] == "Cpd"
            # y for 'yes' (filler value, since true/false is determined by
            # the presence of the key.)
            fields["comp"] = "y"

    elif pos == POS.VERBAL_ADJECTIVE:
        try:
            fields.update(
                {
                    "g": VALUES[data["Gender"]],
                    "c": VALUES[data["Case"]],
                    "n": VALUES[data["Number"]],
                }
            )
        except KeyError:
            assert data["Case"] == "Cpd"
            fields["comp"] = "y"
        fields["f"] = VALUES[data["VerbForm"]]

    elif pos in {POS.INDECLINABLE, POS.VERBAL_INDECLINABLE}:
        pass
    else:
        raise ValueError(f"Unknown part of speech {pos}")
    return ",".join(f"{k}={v}" for k, v in fields.items())


def is_multilemma(token) -> bool:
    """True iff the token covers multiple words. (We ignore these.)"""
    return isinstance(token["id"], tuple)


def iast_to_slp1(s: str) -> str:
    return sanscript.transliterate(s, sanscript.IAST, sanscript.SLP1)


def parse_token(token) -> Token:
    """Parse the token row into a dataclass.

    NOTE: There is no field in the parse data that consistently contains the
    underlying form:

    - `form` is best. But in multi-word chunks, `form` is usually blank.
    - `form_no_sandhi` sometimes does not match the source text.
    - `lemma` is a worst-case backup option.

    We do the best we can, but the data must be cleaned up after.
    """
    form = token["form"]
    if form == "_":
        form = token["form_no_sandhi"]
        if form == "_":
            form = token["lemma"]

    form = iast_to_slp1(form)
    if re.search("[aAiIuUfFxXeEoO][zSr]$", form):
        form = form[:-1] + "H"
    elif form[-1] == "M":
        form = form[:-1] + "m"

    # Other fields are more straightforward.
    lemma = iast_to_slp1(token["lemma"])
    pos = parse_part_of_speech(token["xpos"])
    try:
        tags = create_parse_string(pos, token["tags"])
    except KeyError:
        # The number of ERR tokens should be very small, e.g. there's just
        # one for the Ramayana data.
        tags = f"ERR: {pos}, {token['tags']}"
    return Token(form, lemma, tags)


def parse_phrase(sentence) -> Phrase:
    """Parse the given token list into a phrase.

    :param sentence: a CoNLL-U "sentence," here usually representing a
        half-verse.
    """
    return Phrase(
        raw=sentence.metadata["text_line"],
        slug=sentence.metadata["text_line_counter"],
        tokens=[parse_token(t) for t in sentence if not is_multilemma(t)],
    )


def parse_sections(text: str) -> list[Section]:
    phrases = []
    section_slug = None

    for sentence in conllu.parse(text, fields=FIELDS):
        # Start of section -- extract metadata and continue.
        if "# chapter" in sentence.metadata:
            if phrases:
                yield Section(slug=section_slug, phrases=phrases)
                phrases = []

            section_slug = sentence.metadata["# chapter"]
            continue

        assert section_slug

        # Each "sentence" is a half-verse.
        phrase = parse_phrase(sentence)
        phrases.append(phrase)

    if phrases:
        yield Section(slug=section_slug, phrases=phrases)


def make_block_key(raw: str) -> str:
    # Keep letters, ignoring H due to common typos in the source text.
    key = re.sub(r"([^a-zA-GI-Z])", "", raw)
    # Normalize inconsistent anusvara/parasavarna usage
    key = re.sub("[NYRnm]", "M", key)
    # Normalize certain double consonants
    key = re.sub("tt", "t", key)
    return key


def parse_file(path) -> Iterator[Section]:
    with open(path) as f:
        text = f.read()
    # Make DCS metadata compatible with CONLLU.
    text = re.sub(r"# (\w+):", r"# \1 =", text)
    yield from parse_sections(text)
