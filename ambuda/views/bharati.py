import functools
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, current_app, request, redirect, url_for
from vidyut.kosha import Kosha, PadaEntry, PratipadikaEntry, DhatuEntry
from vidyut.lipi import detect, transliterate, Scheme
from vidyut.prakriya import (
    Vyakarana,
    Gana,
    Linga,
    Vibhakti,
    Purusha,
    Lakara,
    Vacana,
    Prayoga,
    Pada,
    Dhatu,
    Data,
)

from ambuda.views.api import bp as api


bp = Blueprint("bharati", __name__)


@bp.app_template_test("subanta")
def is_vidyut_subanta(x):
    return isinstance(x, PadaEntry.Subanta)


@bp.app_template_test("tinanta")
def is_vidyut_subanta(x):
    return isinstance(x, PadaEntry.Tinanta)


@bp.app_template_test("basic_pratipadika")
def is_vidyut_basic_pratipadka(x):
    return isinstance(x, PratipadikaEntry.Basic)


@bp.app_template_test("krdanta")
def is_vidyut_krdanta(x):
    return isinstance(x, PratipadikaEntry.Krdanta)


@bp.app_template_filter("md")
def slp1_to_devanagari(text: str) -> str:
    # md = "machine devanagari"
    return transliterate(text, Scheme.Slp1, Scheme.Devanagari).replace("*", "\u0970")


@bp.app_template_filter("v_gloss")
def vidyut_gloss(x):
    return GLOSSES.get(x, EMPTY)


@dataclass
class Gloss:
    en_short: str
    en_long: str
    sa_short: str


EMPTY = Gloss(en_short="", en_long="", sa_short="")

GLOSSES = {
    Gana.Bhvadi: Gloss(en_short="1.", en_long="class 1", sa_short="BvAdi*"),
    Gana.Adadi: Gloss(en_short="2.", en_long="class 2", sa_short="adAdi*"),
    Gana.Juhotyadi: Gloss(en_short="3.", en_long="class 3", sa_short="juhotyAdi*"),
    Gana.Divadi: Gloss(en_short="4.", en_long="class 4", sa_short="divAdi*"),
    Gana.Svadi: Gloss(en_short="5.", en_long="class 5", sa_short="svAdi*"),
    Gana.Tudadi: Gloss(en_short="6.", en_long="class 6", sa_short="tudAdi*"),
    Gana.Rudhadi: Gloss(en_short="7.", en_long="class 7", sa_short="ruDAdi*"),
    Gana.Tanadi: Gloss(en_short="8.", en_long="class 8", sa_short="tanAdi*"),
    Gana.Kryadi: Gloss(en_short="9.", en_long="class 9", sa_short="kryAdi*"),
    Gana.Curadi: Gloss(en_short="10.", en_long="class 10", sa_short="curAdi*"),
    Linga.Pum: Gloss(en_short="masc.", en_long="masculine", sa_short="pum*"),
    Linga.Stri: Gloss(en_short="fem.", en_long="feminine", sa_short="strI*"),
    Linga.Napumsaka: Gloss(en_short="neut.", en_long="neuter", sa_short="na*"),
    Vibhakti.Prathama: Gloss(en_short="nom.", en_long="nominative", sa_short="pra*"),
    Vibhakti.Dvitiya: Gloss(en_short="acc.", en_long="accusative", sa_short="dvi*"),
    Vibhakti.Trtiya: Gloss(en_short="ins.", en_long="instrumental", sa_short="tf*"),
    Vibhakti.Caturthi: Gloss(en_short="dat.", en_long="dative", sa_short="ca*"),
    Vibhakti.Panchami: Gloss(en_short="abl.", en_long="ablative", sa_short="pa*"),
    Vibhakti.Sasthi: Gloss(en_short="gen.", en_long="genitive", sa_short="za*"),
    Vibhakti.Saptami: Gloss(en_short="loc.", en_long="locative", sa_short="sa*"),
    Vibhakti.Sambodhana: Gloss(en_short="voc.", en_long="vocative", sa_short="saM*"),
    Prayoga.Kartari: Gloss(en_short="act.", en_long="active", sa_short="kartari"),
    Prayoga.Karmani: Gloss(en_short="pass.", en_long="passive", sa_short="karmaRi"),
    Purusha.Uttama: Gloss(en_short="1st.", en_long="first-person", sa_short="u*"),
    Purusha.Prathama: Gloss(en_short="3rd.", en_long="third-person", sa_short="pra*"),
    Purusha.Madhyama: Gloss(en_short="2nd.", en_long="second-person", sa_short="ma*"),
    Purusha.Uttama: Gloss(en_short="1st.", en_long="first-person", sa_short="u*"),
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
    Vacana.Eka: Gloss(en_short="sg.", en_long="singular", sa_short="eka*"),
    Vacana.Dvi: Gloss(en_short="du.", en_long="dual", sa_short="dvi*"),
    Vacana.Bahu: Gloss(en_short="pl.", en_long="plural", sa_short="bahu*"),
}


@dataclass
class Tinanta:
    """A tinanta-pada with its information."""

    text: str
    dhatu: Dhatu
    purusha: Purusha
    vacana: Vacana
    lakara: Lakara
    prayoga: Prayoga

    @property
    def url(self) -> str:
        spec = "{},{},{},{}".format(
            self.lakara, self.prayoga, self.purusha, self.vacana
        )
        url = url_for(
            "padmini.tinanta_page", dhatu=self.dhatu.upadesha, pada=self.text, spec=spec
        )
        return url


@dataclass
class LakaraTable:
    lakara: str
    prayoga: str
    # tinantas[purusha][vacana] = [padas]
    rows: list[list[list[Tinanta]]]


def _create_lakara_table(dhatu: Dhatu, lakara: Lakara, prayoga: Prayoga) -> LakaraTable:
    tinantas = []
    v = Vyakarana()

    for purusha in [Purusha.Prathama, Purusha.Madhyama, Purusha.Uttama]:
        row = []
        for vacana in [Vacana.Eka, Vacana.Dvi, Vacana.Bahu]:
            cell = []
            prakriyas = v.derive(
                Pada.Tinanta(
                    dhatu=dhatu,
                    lakara=lakara,
                    prayoga=prayoga,
                    purusha=purusha,
                    vacana=vacana,
                )
            )
            for p in prakriyas:
                text = p.text
                if text.endswith("d"):
                    continue

                tinanta = Tinanta(
                    text=p.text,
                    dhatu=dhatu,
                    purusha=purusha,
                    vacana=vacana,
                    prayoga=prayoga,
                    lakara=lakara,
                )
                cell.append(tinanta)
            cell = sorted(cell, key=lambda x: x.text)
            row.append(cell)
        tinantas.append(row)

    return LakaraTable(lakara=str(lakara), prayoga=str(prayoga), rows=tinantas)


@functools.cache
def get_kosha():
    return Kosha(Path(current_app.config["VIDYUT_DATA_DIR"]) / "kosha")


@functools.cache
def get_dhatus() -> map:
    entries = Data(
        Path(current_app.config["VIDYUT_DATA_DIR"]) / "prakriya"
    ).load_dhatu_entries()
    map = {}
    for e in entries:
        key = f"{e.dhatu.aupadeshika}-{str(e.dhatu.gana)}"
        map[key] = e
    return map


def _get_kosha_entries(raw_query: str) -> list:
    query = raw_query.strip()
    if not query:
        return []

    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    if query[-1] in "Hr":
        query = query[:-1] + "s"

    kosha = get_kosha()
    return kosha.get(query)


@bp.route("/")
def index():
    query = request.args.get("q", "").strip()
    if not query:
        return render_template("bharati/index.html")

    entries = _get_kosha_entries(query)
    return render_template("bharati/query.html", query=query, entries=entries)


@bp.route("/dhatus/<path>")
def dhatu(path):
    input_scheme = detect(path) or Scheme.Devanagari
    dhatu_key = transliterate(path, input_scheme, Scheme.Slp1)

    dhatu_map = get_dhatus()
    try:
        dhatu_entry = dhatu_map[dhatu_key]
    except KeyError:
        return redirect(url_for("bharati.index"))

    dhatu = dhatu_entry.dhatu
    lakaras = []
    for la in [
        Lakara.Lat,
        Lakara.Lit,
        Lakara.Lut,
        Lakara.Lrt,
        Lakara.Lot,
        Lakara.Lan,
        Lakara.VidhiLin,
        Lakara.AshirLin,
        Lakara.Lun,
    ]:
        lakaras.append(_create_lakara_table(dhatu, la, Prayoga.Kartari))
    return render_template(
        "bharati/dhatu.html", dhatu_entry=dhatu_entry, lakaras=lakaras
    )


@api.route("/bharati/query/<query>")
def bharati_query(query):
    query = query.strip()
    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    entries = _get_kosha_entries(query)
    return render_template("htmx/bharati-query.html", query=query, entries=entries)
