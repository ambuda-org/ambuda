import functools
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, current_app, request, redirect, url_for
from vidyut.kosha import Kosha, PadaEntry, PratipadikaEntry
from vidyut.lipi import detect, transliterate, Scheme
from vidyut.prakriya import Linga, Vibhakti, Purusha, Lakara, Vacana, Prayoga

from ambuda.views.api import bp as api


bp = Blueprint("bharati", __name__)


@dataclass
class Gloss:
    en_short: str
    en_long: str
    sa_short: str


EMPTY = Gloss(en_short="", en_long="", sa_short="")

LINGAS = {
    Linga.Pum: Gloss(en_short="masc.", en_long="masculine", sa_short="pum*"),
    Linga.Stri: Gloss(en_short="fem.", en_long="feminine", sa_short="strI*"),
    Linga.Napumsaka: Gloss(en_short="neut.", en_long="neuter", sa_short="na*"),
}

VIBHAKTIS = {
    Vibhakti.Prathama: Gloss(en_short="nom.", en_long="nominative", sa_short="pra*"),
    Vibhakti.Dvitiya: Gloss(en_short="acc.", en_long="accusative", sa_short="dvi*"),
    Vibhakti.Trtiya: Gloss(en_short="ins.", en_long="instrumental", sa_short="tf*"),
    Vibhakti.Caturthi: Gloss(en_short="dat.", en_long="dative", sa_short="ca*"),
    Vibhakti.Panchami: Gloss(en_short="abl.", en_long="ablative", sa_short="pa*"),
    Vibhakti.Sasthi: Gloss(en_short="gen.", en_long="genitive", sa_short="za*"),
    Vibhakti.Saptami: Gloss(en_short="loc.", en_long="locative", sa_short="sa*"),
    Vibhakti.Sambodhana: Gloss(en_short="voc.", en_long="vocative", sa_short="saM*"),
}

PURUSHAS = {
    Purusha.Prathama: Gloss(en_short="3rd.", en_long="third-person", sa_short="pra*"),
    Purusha.Madhyama: Gloss(en_short="2nd.", en_long="second-person", sa_short="ma*"),
    Purusha.Uttama: Gloss(en_short="1st.", en_long="first-person", sa_short="u*"),
}

LAKARAS = {
    Lakara.Lat: Gloss(en_short="pres.", en_long="present indicative", sa_short="law"),
    Lakara.Lit: Gloss(en_short="perf.", en_long="perfect", sa_short="liw"),
    Lakara.Lut: Gloss(
        en_short="p. fut.", en_long="periphrastic future", sa_short="luw"
    ),
    Lakara.Lrt: Gloss(en_short="fut.", en_long="simple future", sa_short="lfw"),
    Lakara.Lot: Gloss(en_short="impv.", en_long="imperative", sa_short="low"),
    Lakara.Lan: Gloss(en_short="impf.", en_long="imperfect", sa_short="laN"),
    Lakara.VidhiLin: Gloss(en_short="opt.", en_long="optative", sa_short="viDiliN"),
    Lakara.AshirLin: Gloss(en_short="ben.", en_long="benedictive", sa_short="AzIrliN"),
    Lakara.Lun: Gloss(en_short="aor.", en_long="aorist", sa_short="luN"),
    Lakara.Lrn: Gloss(en_short="cond.", en_long="conditional", sa_short="lfN"),
}

VACANAS = {
    Vacana.Eka: Gloss(en_short="sg.", en_long="singular", sa_short="eka*"),
    Vacana.Dvi: Gloss(en_short="du.", en_long="dual", sa_short="dvi*"),
    Vacana.Bahu: Gloss(en_short="pl.", en_long="plural", sa_short="bahu*"),
}


@dataclass
class Card:
    entry: PadaEntry

    @property
    def lemma(self):
        match self.entry:
            case PadaEntry.Tinanta():
                dhatu_entry = self.entry.dhatu_entry
                dhatu = dhatu_entry.clean_text
                aupadeshika = dhatu_entry.dhatu.aupadeshika
                artha_sa = dhatu_entry.artha_sa
                return f"{dhatu} ({aupadeshika} {artha_sa})"
            case PadaEntry.Subanta():
                phit_entry = self.entry.pratipadika_entry
                match phit_entry:
                    case PratipadikaEntry.Krdanta():
                        return phit_entry.dhatu_entry.clean_text
                    case PratipadikaEntry.Basic():
                        return phit_entry.pratipadika.text
                    case _:
                        return str(self.entry)
                return str(self.entry)
            case _:
                return "---"

    @property
    def parse(self):
        match self.entry:
            case PadaEntry.Tinanta():
                p = PURUSHAS[self.entry.purusha].sa_short
                v = VACANAS[self.entry.vacana].sa_short
                la = LAKARAS[self.entry.lakara].sa_short
                return f"{p} {v} {la}".replace("*", "\u0970")
            case PadaEntry.Subanta():
                li = LINGAS.get(self.entry.linga, EMPTY).sa_short
                vi = VIBHAKTIS.get(self.entry.vibhakti, EMPTY).sa_short
                va = VACANAS.get(self.entry.vacana, EMPTY).sa_short
                return f"{li} {vi} {va}".replace("*", "\u0970")


@functools.cache
def get_kosha():
    return Kosha(Path(current_app.config["VIDYUT_DATA_DIR"]) / "kosha")


def _get_kosha_entries(raw_query: str) -> list:
    query = raw_query.strip()
    if not query:
        return []

    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    if query[-1] in "Hr":
        query = query[:-1] + "s"

    kosha = get_kosha()
    entries = kosha.get(query)

    return [Card(e) for e in entries]


@bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("bharati/index.html")

    entries = _get_kosha_entries(query)
    return render_template("bharati/query.html", query=query, entries=entries)


@api.route("/bharati/query/<query>")
def bharati_query(query):
    query = query.strip()
    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    entries = _get_kosha_entries(query)
    return render_template("htmx/bharati-query.html", query=query, entries=entries)
