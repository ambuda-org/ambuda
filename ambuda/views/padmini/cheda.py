from dataclasses import dataclass
from vidyut.cheda import Token
from vidyut.kosha import Pada, Linga, Vibhakti, Vacana, Lakara, Purusha, PartOfSpeech
from ambuda.views.padmini.resources import get_chedaka


# Vidyut enums are currently unhashable, so model as list
LINGAS = [
    (Linga.Pum, "masc."),
    (Linga.Stri, "fem."),
    (Linga.Napumsaka, "neut."),
]

SA_LINGAS = [
    (Linga.Pum, "pum*"),
    (Linga.Stri, "strI*"),
    (Linga.Napumsaka, "na*"),
]

VIBHAKTIS = [
    (Vibhakti.V1, "nom."),
    (Vibhakti.V2, "acc."),
    (Vibhakti.V3, "ins."),
    (Vibhakti.V4, "dat."),
    (Vibhakti.V5, "abl."),
    (Vibhakti.V6, "gen."),
    (Vibhakti.V7, "loc."),
    (Vibhakti.Sambodhana, "voc."),
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
    (Purusha.Prathama, "3rd."),
    (Purusha.Madhyama, "2nd."),
    (Purusha.Uttama, "1st."),
]

SA_PURUSHAS = [
    (Purusha.Prathama, "pra*"),
    (Purusha.Madhyama, "ma*"),
    (Purusha.Uttama, "u*"),
]

LAKARAS = [
    (Lakara.Lat, "pres."),
    (Lakara.Lit, "perf."),
    (Lakara.Lut, "p. fut."),
    (Lakara.Lrt, "fut."),
    (Lakara.Lot, "impv."),
    (Lakara.Lan, "impf."),
    (Lakara.VidhiLin, "opt."),
    (Lakara.AshirLin, "ben."),
    (Lakara.Lun, "aor."),
    (Lakara.Lrn, "cond."),
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
    (Vacana.Eka, "sg."),
    (Vacana.Dvi, "du."),
    (Vacana.Bahu, "pl."),
]

SA_VACANAS = [
    (Vacana.Eka, "eka*"),
    (Vacana.Dvi, "dvi*"),
    (Vacana.Bahu, "bahu*"),
]


def lookup(items, needle) -> str:
    for k, v in items:
        if needle == k:
            return v
    return ""


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
    def gloss(self):
        buf = []
        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            buf.append(lookup(LINGAS, self.info.linga))
            buf.append(lookup(VIBHAKTIS, self.info.vibhakti))
            buf.append(lookup(VACANAS, self.info.vacana))
            if self.info.is_purvapada:
                buf.append("comp.")

        elif pos == PartOfSpeech.Tinanta:
            buf.append(lookup(PURUSHAS, self.info.purusha))
            buf.append(lookup(VACANAS, self.info.vacana))
            buf.append(lookup(LAKARAS, self.info.lakara))
            if self.info.is_purvapada:
                buf.append("comp.")

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
