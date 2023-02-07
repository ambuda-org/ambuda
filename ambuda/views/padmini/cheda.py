from dataclasses import dataclass
from vidyut.cheda import Token
from vidyut.kosha import Pada, Linga, Vibhakti, Vacana, Lakara, Purusha, PartOfSpeech
from ambuda.views.padmini.resources import get_chedaka


@dataclass
class Gloss:
    short: str
    long: str


AVYAYA = Gloss(short="ind.", long="indeclinable")
SAMASTA = Gloss(short="comp.", long="compounded")


# Vidyut enums are currently unhashable, so model as list
LINGAS = [
    (Linga.Pum, Gloss(short="masc.", long="masculine")),
    (Linga.Stri, Gloss(short="fem.", long="feminine")),
    (Linga.Napumsaka, Gloss(short="neut.", long="neuter")),
]

SA_LINGAS = [
    (Linga.Pum, "pum*"),
    (Linga.Stri, "strI*"),
    (Linga.Napumsaka, "na*"),
]

VIBHAKTIS = [
    (Vibhakti.V1, Gloss(short="nom.", long="nominative")),
    (Vibhakti.V2, Gloss(short="acc.", long="accusative")),
    (Vibhakti.V3, Gloss(short="ins.", long="instrumental")),
    (Vibhakti.V4, Gloss(short="dat.", long="dative")),
    (Vibhakti.V5, Gloss(short="abl.", long="ablative")),
    (Vibhakti.V6, Gloss(short="gen.", long="genitive")),
    (Vibhakti.V7, Gloss(short="loc.", long="locative")),
    (Vibhakti.Sambodhana, Gloss(short="voc.", long="vocative")),
]

SA_VIBHAKTIS = [
    (Vibhakti.V1, "pra*"),
    (Vibhakti.V2, "dvi*"),
    (Vibhakti.V3, "tf*"),
    (Vibhakti.V4, "ca*"),
    (Vibhakti.V5, "pa*"),
    (Vibhakti.V6, "Sa*"),
    (Vibhakti.V7, "sa*"),
    (Vibhakti.Sambodhana, "saM*"),
]

PURUSHAS = [
    (Purusha.Prathama, Gloss(short="3rd.", long="third-person")),
    (Purusha.Madhyama, Gloss(short="2nd.", long="second-person")),
    (Purusha.Uttama, Gloss(short="1st.", long="first-person")),
]

SA_PURUSHAS = [
    (Purusha.Prathama, "pra*"),
    (Purusha.Madhyama, "ma*"),
    (Purusha.Uttama, "u*"),
]

LAKARAS = [
    (Lakara.Lat, Gloss(short="pres.", long="present indicative")),
    (Lakara.Lit, Gloss(short="perf.", long="perfect")),
    (Lakara.Lut, Gloss(short="p. fut.", long="periphrastic future")),
    (Lakara.Lrt, Gloss(short="fut.", long="simple future")),
    (Lakara.Lot, Gloss(short="impv.", long="imperative")),
    (Lakara.Lan, Gloss(short="impf.", long="imperfect")),
    (Lakara.VidhiLin, Gloss(short="opt.", long="optative")),
    (Lakara.AshirLin, Gloss(short="ben.", long="benedictive")),
    (Lakara.Lun, Gloss(short="aor.", long="aorist")),
    (Lakara.Lrn, Gloss(short="cond.", long="conditional")),
]

SA_LAKARAS = [
    (Lakara.Lat, "lfw"),
    (Lakara.Lit, "lfw"),
    (Lakara.Lut, "lfw"),
    (Lakara.Lrt, "lfw"),
    (Lakara.Lot, "low"),
    (Lakara.Lan, "laN"),
    (Lakara.VidhiLin, "viDiliN"),
    (Lakara.AshirLin, "AzIrliN"),
    (Lakara.Lun, "luN"),
    (Lakara.Lrn, "lfN"),
]

VACANAS = [
    (Vacana.Eka, Gloss(short="sg.", long="singular")),
    (Vacana.Dvi, Gloss(short="du.", long="dual")),
    (Vacana.Bahu, Gloss(short="pl.", long="plural")),
]

SA_VACANAS = [
    (Vacana.Eka, "eka*"),
    (Vacana.Dvi, "dvi*"),
    (Vacana.Bahu, "bahu*"),
]


def lookup(items, needle) -> Gloss:
    for k, v in items:
        if needle == k:
            return v
    return Gloss(short="", long="")


@dataclass
class DisplayToken:
    """Wrapper for vidyut_cheda.Token with useful display methods."""

    text: str
    lemma: str
    info: Pada

    @property
    def separator(self) -> str:
        if self.info.is_purvapada:
            return "-"
        else:
            return " "

    @property
    def classes(self) -> str:
        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            return "bg-green-200"
        elif pos == PartOfSpeech.Tinanta:
            return "bg-yellow-200"
        elif pos == PartOfSpeech.Avyaya:
            return "bg-sky-100"
        else:
            return "bg-slate-200"

    @property
    def is_sanskrit(self) -> bool:
        return self.info.pos is not None

    @property
    def short_gloss(self):
        """Return a human-readable gloss of this token."""
        buf = []

        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            buf.append(lookup(LINGAS, self.info.linga).short)
            buf.append(lookup(VIBHAKTIS, self.info.vibhakti).short)
            buf.append(lookup(VACANAS, self.info.vacana).short)
            if self.info.is_purvapada:
                buf.append(SAMASTA.short)

        elif pos == PartOfSpeech.Tinanta:
            buf.append(lookup(PURUSHAS, self.info.purusha).short)
            buf.append(lookup(VACANAS, self.info.vacana).short)
            buf.append(lookup(LAKARAS, self.info.lakara).short)

        elif pos == PartOfSpeech.Avyaya:
            buf.append(AVYAYA.short)

        return " ".join(buf)

    @property
    def long_gloss(self):
        """Return a human-readable description of this token."""
        buf = []
        pos = self.info.pos
        print(pos)
        if pos == PartOfSpeech.Subanta:
            buf.append("nominal,")
            buf.append(lookup(LINGAS, self.info.linga).long)
            buf.append(lookup(VIBHAKTIS, self.info.vibhakti).long)
            buf.append(lookup(VACANAS, self.info.vacana).long)
            if self.info.is_purvapada:
                buf.append(SAMASTA.long)

        elif pos == PartOfSpeech.Tinanta:
            buf.append("verb,")
            buf.append(lookup(PURUSHAS, self.info.purusha).long)
            buf.append(lookup(VACANAS, self.info.vacana).long)
            buf.append(lookup(LAKARAS, self.info.lakara).long)

        elif pos == PartOfSpeech.Avyaya:
            buf.append(AVYAYA.long)

        else:
            buf.append("(unknown)")

        return " ".join(buf)


def _convert_to_display_tokens(tokens: list[Token]) -> list[DisplayToken]:
    # Most users expect and prefer the visarga as opposed to a word-final "s"
    # or "r".
    ret = []
    for t in tokens:
        text = t.text
        if text.endswith("s") or text.endswith("r"):
            text = text[:-1] + "H"

        ret.append(
            DisplayToken(
                text=text,
                lemma=t.lemma or "",
                info=t.info,
            )
        )
    return ret


def create_results(slp1_query: str) -> list[DisplayToken]:
    """Handle the user's query and create a result set."""

    chedaka = get_chedaka()
    try:
        tokens = chedaka.run(slp1_query)
    except Exception:
        # TODO: For now, use an exhaustive exception guard. As `vidyut`
        # matures, see if we can avoid most or all exceptions here.
        tokens = []

    return _convert_to_display_tokens(tokens)
