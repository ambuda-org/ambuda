from dataclasses import dataclass

from vidyut.cheda import Token
from vidyut.kosha import Lakara, Linga, Pada, PartOfSpeech, Purusha, Vacana, Vibhakti

from ambuda.views.padmini.resources import get_chedaka


@dataclass
class Gloss:
    """Stores the various ways to translate some grammatical term."""

    short: str
    long: str
    sa_short: str = ""


AVYAYA = Gloss(short="ind.", long="indeclinable")
SAMASTA = Gloss(short="comp.", long="compounded")
EMPTY = Gloss(short="", long="")


LINGAS = {
    Linga.Pum: Gloss(short="masc.", long="masculine", sa_short="pum*"),
    Linga.Stri: Gloss(short="fem.", long="feminine", sa_short="strI*"),
    Linga.Napumsaka: Gloss(short="neut.", long="neuter", sa_short="na*"),
    None: EMPTY,
}

VIBHAKTIS = {
    Vibhakti.V1: Gloss(short="nom.", long="nominative", sa_short="pra*"),
    Vibhakti.V2: Gloss(short="acc.", long="accusative", sa_short="dvi*"),
    Vibhakti.V3: Gloss(short="ins.", long="instrumental", sa_short="tf*"),
    Vibhakti.V4: Gloss(short="dat.", long="dative", sa_short="ca*"),
    Vibhakti.V5: Gloss(short="abl.", long="ablative", sa_short="pa*"),
    Vibhakti.V6: Gloss(short="gen.", long="genitive", sa_short="Sa*"),
    Vibhakti.V7: Gloss(short="loc.", long="locative", sa_short="sa*"),
    Vibhakti.Sambodhana: Gloss(short="voc.", long="vocative", sa_short="saM*"),
    None: EMPTY,
}

PURUSHAS = {
    Purusha.Prathama: Gloss(short="3rd.", long="third-person", sa_short="pra*"),
    Purusha.Madhyama: Gloss(short="2nd.", long="second-person", sa_short="ma*"),
    Purusha.Uttama: Gloss(short="1st.", long="first-person", sa_short="u*"),
}

LAKARAS = {
    Lakara.Lat: Gloss(short="pres.", long="present indicative", sa_short="law"),
    Lakara.Lit: Gloss(short="perf.", long="perfect", sa_short="liw"),
    Lakara.Lut: Gloss(short="p. fut.", long="periphrastic future", sa_short="luw"),
    Lakara.Lrt: Gloss(short="fut.", long="simple future", sa_short="lfw"),
    Lakara.Lot: Gloss(short="impv.", long="imperative", sa_short="low"),
    Lakara.Lan: Gloss(short="impf.", long="imperfect", sa_short="laN"),
    Lakara.VidhiLin: Gloss(short="opt.", long="optative", sa_short="viDiliN"),
    Lakara.AshirLin: Gloss(short="ben.", long="benedictive", sa_short="AzIrliN"),
    Lakara.Lun: Gloss(short="aor.", long="aorist", sa_short="luN"),
    Lakara.Lrn: Gloss(short="cond.", long="conditional", sa_short="lfN"),
}

VACANAS = {
    Vacana.Eka: Gloss(short="sg.", long="singular", sa_short="eka*"),
    Vacana.Dvi: Gloss(short="du.", long="dual", sa_short="dvi*"),
    Vacana.Bahu: Gloss(short="pl.", long="plural", sa_short="bahu*"),
    None: EMPTY,
}


@dataclass
class DisplayToken:
    """Wrapper for vidyut_cheda.Token with useful display methods."""

    text: str
    lemma: str
    info: Pada

    @property
    def separator(self) -> str:
        """The separator that should follow this token.

        This is `-` for compounds and a space otherwise.
        """
        if self.info.is_purvapada:
            return "-"
        else:
            return " "

    @property
    def classes(self) -> str:
        """The CSS classes that should be used for this token.

        We currently choose CSS classes based on the token's part of speech.
        """
        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            return "bg-yellow-200 dark:bg-transparent dark:text-yellow-500 dark:border dark:border-yellow-500"
        elif pos == PartOfSpeech.Tinanta:
            return "bg-sky-200"
        elif pos == PartOfSpeech.Avyaya:
            return "bg-slate-100"
        else:
            return "bg-white outline outline-slate-300 outline-1"

    @property
    def is_sanskrit(self) -> bool:
        """Return whether or not this token is part of a Sanskrit word."""
        return self.info.pos is not None

    @property
    def short_gloss(self):
        """Return a short human-readable gloss of this token."""
        buf = []
        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            buf.extend(
                [
                    LINGAS[self.info.linga].short,
                    VIBHAKTIS[self.info.vibhakti].short,
                    VACANAS[self.info.vacana].short,
                ]
            )
            if self.info.is_purvapada:
                buf.append(SAMASTA.short)

        elif pos == PartOfSpeech.Tinanta:
            buf.extend(
                [
                    PURUSHAS[self.info.purusha].short,
                    VACANAS[self.info.vacana].short,
                    LAKARAS[self.info.lakara].short,
                ]
            )

        elif pos == PartOfSpeech.Avyaya:
            buf.append(AVYAYA.short)

        return " ".join(buf)

    @property
    def long_gloss(self):
        """Return a longer human-readable description of this token."""
        buf = []
        pos = self.info.pos
        if pos == PartOfSpeech.Subanta:
            buf.append("nominal,")
            buf.extend(
                [
                    LINGAS[self.info.linga].long,
                    VIBHAKTIS[self.info.vibhakti].long,
                    VACANAS[self.info.vacana].long,
                ]
            )
            if self.info.is_purvapada:
                buf.append(SAMASTA.long)

        elif pos == PartOfSpeech.Tinanta:
            buf.append("verb,")
            buf.extend(
                [
                    PURUSHAS[self.info.purusha].long,
                    VACANAS[self.info.vacana].long,
                    LAKARAS[self.info.lakara].long,
                ]
            )

        elif pos == PartOfSpeech.Avyaya:
            buf.append(AVYAYA.long)

        else:
            buf.append("(unknown)")

        return " ".join(buf)


@dataclass
class TokenSpan:
    """A sequence of tokens that form a logical unit.

    Examples: compounded words, consecutive punctuation tokens
    """

    tokens: list[DisplayToken]

    @property
    def last(self) -> DisplayToken:
        """The last token in this span."""
        return self.tokens[-1]


def _create_display_token(t: Token) -> DisplayToken:
    """Convert a `vidyut.cheda.Token` into a structure ready for display."""

    # Most users expect and prefer the visarga as opposed to a word-final "s"
    # or "r".
    text = t.text
    if text.endswith("s") or text.endswith("r"):
        text = text[:-1] + "H"

    return DisplayToken(
        text=text,
        lemma=t.lemma or "",
        info=t.info,
    )


def _convert_to_display_tokens(tokens: list[Token]) -> list[TokenSpan]:
    """Convert `vidyut.cheda` tokens into display spans."""
    ret = []
    span = []
    for t in tokens:
        display_token = _create_display_token(t)
        span.append(display_token)

        is_end_of_compound = not display_token.info.is_purvapada
        is_end_of_span = is_end_of_compound
        if is_end_of_span:
            ret.append(TokenSpan(tokens=span))
            span = []
    return ret


def create_results(slp1_query: str) -> list[TokenSpan]:
    """Handle the user's query and create a result set."""

    chedaka = get_chedaka()
    try:
        tokens = chedaka.run(slp1_query)
    except Exception:
        # TODO: For now, use an exhaustive exception guard. As `vidyut`
        # matures, see if we can avoid most or all exceptions here.
        tokens = []

    return _convert_to_display_tokens(tokens)
