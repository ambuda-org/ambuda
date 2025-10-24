import functools
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, render_template, current_app, request, redirect, url_for
from vidyut.kosha import Kosha, PadaEntry, PratipadikaEntry, DhatuEntry
from vidyut.lipi import detect, transliterate, Scheme
from vidyut.prakriya import (
    Vyakarana,
    Prakriya,
    Gana,
    Linga,
    Vibhakti,
    Purusha,
    Krt,
    Lakara,
    Vacana,
    Prayoga,
    Pada,
    Dhatu,
    Data,
    DhatuPada,
)

from ambuda.views.api import bp as api


bp = Blueprint("bharati", __name__)


MINOR_RULES = {
    # it
    "1.3.2",
    "1.3.3",
    "1.3.4",
    "1.3.5",
    "1.3.6",
    "1.3.7",
    "1.3.8",
    "1.3.9",
    # atidesha
    "1.2.4",
    # samjna
    "1.4.13",
    "1.4.14",
    "3.4.113",
    "3.4.114",
    "3.4.115",
    "6.1.4",
    "6.1.5",
    # tripadi
    "8.3.111",
    "8.4.68",
}


# TODO: `Anubandha` is not exported in 0.4.0. Once 0.4.1 is available, switch string keys to enum.
DHATU_ANUBANDHAS = {
    "adit": [("Has no meaning and usually serves as a placeholder.", None)],
    "Adit": [],
    "idit": [("Adds [[nu~m]].", "7.1.58")],
    "Idit": [],
    "udit": [],
    "Udit": [],
    "fdit": [],
    "xdit": [("Uses [[aN]] when forming [[luN-lakAra]].", "3.1.55")],
    "edit": [("Prevents [[vfdDi]] in [[luN-lakAra]] when used with [[iw]].", "7.2.5")],
    "odit": [("Causes the [[t]] of [[kta]] to change to [[n]].", "8.2.45")],
    "qvit": [("Can use the suffix [[ktri]].", "3.3.88")],
    "wvit": [("Can use the suffix [[Tuc]].", "3.3.89")],
}


# TODO: `Anubandha` is not exported in 0.4.0. Once 0.4.1 is available, switch string keys to enum.
KRT_ANUBANDHAS = {
    "idit": [("Has no meaning and usually serves as a placeholder.", None)],
    "udit": [
        ("Adds [[nu~m]] to the base in the strong cases.", "7.1.70"),
        ("Forms its feminine stem with [[NIp]].", "4.1.6"),
    ],
    "fdit": [
        ("Adds [[nu~m]] to the base in the strong cases.", "7.1.70"),
        ("Forms its feminine stem with [[NIp]].", "4.1.6"),
    ],
    "kit": [
        ("Blocks [[guRa]] on the base's last vowel.", "1.1.5"),
        ("Causes [[samprasAraRa]] on various roots.", "6.1.15"),
    ],
    "Kit": [
        ("Adds [[m]] after a compound's first member if it ends in a vowel.", "6.3.67"),
        (
            "Shortens the last vowel of the compound's first member if it is not an indeclinable.",
            "6.3.66",
        ),
    ],
    "Git": [
        (
            "Changes the base's final [[c]] or [[j]] to change to [[k]] or [[g]], respectively.",
            "7.3.52",
        ),
    ],
    "Nit": [
        ("Blocks [[guRa]] on the base's last vowel.", "1.1.5"),
        ("Causes [[samprasAraRa]] on various roots.", "6.1.16"),
    ],
    "cit": [("Causes [[udAtta]] accent on the stem's last vowel.", "6.1.163")],
    "Yit": [
        ("Causes [[vfdDi]] of the base's last vowel.", "7.2.115"),
        ("Causes [[udAtta]] accent on the stem's first vowel.", "6.1.197"),
    ],
    "wit": [("Forms its feminine step with [[NIp]].", "4.1.15")],
    "Rit": [("Causes [[vfdDi]] of the base's last vowel.", "7.2.115")],
    "tit": [("Causes [[svarita]] on the suffix's first vowel.", "6.1.185")],
    "nit": [("Causes [[udAtta]] accent on the stem's first vowel.", "6.1.197")],
    "pit": [
        ("Causes all vowels in the suffix to be [[anudAtta]].", "3.1.4"),
    ],
    "rit": [("Causes [[udAtta]] accent on the suffix's penultimate vowel.", "6.1.217")],
    "lit": [
        ("Causes [[udAtta]] accent on the base's last vowel.", "6.1.193"),
    ],
    "Sit": [
        ("Causes [[sArvaDAtuka]] changes, such as base substitution.", "3.4.113"),
    ],
    "zit": [("Forms its feminine stem with [[NIz]].", "4.1.41")],
    "sit": [
        (
            "Causes the base to be called [[pada]], which allows certain sound rules.",
            "1.4.16",
        ),
    ],
}


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


def to_slp1(x: str) -> str:
    return transliterate(x, Scheme.Devanagari, Scheme.Slp1)


@dataclass
class Tinanta:
    """A tinanta-pada with its information."""

    text: str
    dhatu: Dhatu
    purusha: Purusha
    vacana: Vacana
    lakara: Lakara
    prayoga: Prayoga
    dhatu_pada: DhatuPada

    @property
    def url(self) -> str:
        dhatu = self.dhatu
        dhatu_spec = "{}-{}".format(dhatu.aupadeshika, str(dhatu.gana))

        pada_spec = "{}-{}-{}-{}-{}".format(
            self.text, self.prayoga, self.lakara, self.purusha, self.vacana
        )

        dhatu_spec = transliterate(dhatu_spec, Scheme.Slp1, Scheme.Devanagari)
        pada_spec = transliterate(pada_spec, Scheme.Slp1, Scheme.Devanagari)
        url = url_for(
            "bharati.tinanta",
            dhatu=dhatu_spec,
            pada=pada_spec,
        )
        return url


@dataclass
class LakaraTable:
    lakara: str
    prayoga: str
    pada: str
    # tinantas[purusha][vacana] = [padas]
    rows: list[list[list[Tinanta]]]


def _create_lakara_table(
    dhatu: Dhatu, *, lakara: Lakara, prayoga: Prayoga, pada: DhatuPada
) -> LakaraTable | None:
    tinantas = []
    v = Vyakarana()

    had_any = False
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
                    dhatu_pada=pada,
                )
            )
            if prakriyas:
                had_any = True

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
                    dhatu_pada=pada,
                )
                cell.append(tinanta)

            cell = sorted(cell, key=lambda x: x.text)
            row.append(cell)
        tinantas.append(row)

    if had_any:
        return LakaraTable(
            lakara=str(lakara), prayoga=str(prayoga), pada=str(pada), rows=tinantas
        )
    else:
        return None


@functools.cache
def get_kosha():
    return Kosha(Path(current_app.config["VIDYUT_DATA_DIR"]) / "kosha")


@functools.cache
def get_dhatu_entries() -> dict:
    entries = Data(
        Path(current_app.config["VIDYUT_DATA_DIR"]) / "prakriya"
    ).load_dhatu_entries()
    map = {}

    v = Vyakarana()
    for e in entries:
        aupadeshika_no_svara = e.dhatu.aupadeshika.replace("\\", "").replace("^", "")
        key = f"{aupadeshika_no_svara}-{str(e.dhatu.gana)}"
        map[key] = e
    return map


@functools.cache
def get_sutras() -> dict:
    entries = Data(
        Path(current_app.config["VIDYUT_DATA_DIR"]) / "prakriya"
    ).load_sutras()
    return {(e.source, e.code): e.text for e in entries}


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


@api.route("/bharati/query/<query>")
def bharati_query(query):
    query = query.strip()
    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    entries = _get_kosha_entries(query)
    return render_template("htmx/bharati-query.html", query=query, entries=entries)


@bp.route("/dhatus/<dhatu_spec>")
def dhatu(dhatu_spec):
    input_scheme = detect(dhatu_spec) or Scheme.Devanagari
    dhatu_key = transliterate(dhatu_spec, input_scheme, Scheme.Slp1)
    dhatu_key = dhatu_key.replace("^", "").replace("\\", "")

    dhatu_map = get_dhatu_entries()
    try:
        dhatu_entry = dhatu_map[dhatu_key]
    except KeyError:
        return redirect(url_for("bharati.index"))

    meanings = []
    # anubandhas = dhatu_entry.dhatu.anubandhas()
    # for a in anubandhas:
    #     raw_messages = DHATU_ANUBANDHAS.get(str(a), [("(no information found)", "--")])
    #     meanings.append((a, raw_messages))

    dhatu = dhatu_entry.dhatu
    tinantas = []
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
        lakara = []
        for pada in [DhatuPada.Parasmaipada, DhatuPada.Atmanepada]:
            lakara.append(
                _create_lakara_table(
                    dhatu, lakara=la, prayoga=Prayoga.Kartari, pada=pada
                )
            )
        tinantas.append(lakara)

    return render_template(
        "bharati/dhatu.html",
        dhatu_entry=dhatu_entry,
        meanings=meanings,
        tinantas=tinantas,
    )


@bp.route("/k/")
def krt_list():
    all_krts = Krt.choices()
    return render_template("bharati/krt-list.html", krts=all_krts)


@bp.route("/k/<krt>")
def krt(krt):
    krt_slp = to_slp1(krt)
    try:
        krt = Krt(krt_slp)
    except ValueError:
        return redirect(url_for("bharati.krt_list"))

    all_meanings = []
    anubandhas = krt.anubandhas()
    if "yu~" in krt_slp or "vu~" in krt_slp:
        anubandhas = [x for x in anubandhas if str(x) != "udit"]
    if "vi~" in krt_slp:
        anubandhas = [x for x in anubandhas if str(x) != "idit"]

    meanings = []
    for a in anubandhas:
        raw_messages = KRT_ANUBANDHAS.get(str(a), [("(no information found)", "--")])
        messages = []
        for message, code in raw_messages:
            message = message.replace("[[", "`").replace("]]", "`")
            fragments = message.split("`")
            buf = []
            for i, fragment in enumerate(fragments):
                if i % 2 == 0:
                    buf.append(fragment)
                else:
                    buf.append(transliterate(fragment, Scheme.Slp1, Scheme.Devanagari))
            message = "".join(buf)
            messages.append((message, code))
        meanings.append((a, messages))

    return render_template("bharati/krt.html", krt=krt, meanings=meanings)


@bp.route("/dhatus/<dhatu>/tin/<pada>")
def tinanta(dhatu, pada):
    aupadeshika, gana = transliterate(dhatu, Scheme.Devanagari, Scheme.Slp1).split("-")
    raw_pada, prayoga, lakara, purusha, vacana = transliterate(
        pada, Scheme.Devanagari, Scheme.Slp1
    ).split("-")

    all_dhatus = get_dhatu_entries()
    dhatu_key = transliterate(dhatu, Scheme.Devanagari, Scheme.Slp1)
    dhatu_key = dhatu_key.replace("^", "").replace("\\", "")
    dhatu_entry = all_dhatus.get(dhatu_key)
    if not dhatu_entry:
        return redirect(url_for("bharati.index"))

    v = Vyakarana()

    prakriyas = v.derive(
        Pada.Tinanta(
            dhatu=Dhatu.mula(aupadeshika, Gana(gana)),
            lakara=Lakara(lakara),
            prayoga=Prayoga(prayoga),
            purusha=Purusha(purusha),
            vacana=Vacana(vacana),
            dhatu_pada=DhatuPada.Parasmaipada,
        )
    )
    prakriya = next(p for p in prakriyas if p.text == raw_pada)
    if not prakriya:
        return redirect(url_for("bharati.dhatu", dhatu_spec=dhatu))

    q = transliterate(raw_pada, Scheme.Slp1, Scheme.Devanagari)
    short_history = []
    all_sutras = get_sutras()
    for s in prakriya.history:
        if s.code in MINOR_RULES:
            continue
        sutra_url = f"https://ashtadhyayi.com/sutraani/{s.code}"
        sutra_text = all_sutras.get((s.source, s.code))
        short_history.append((s, sutra_text, sutra_url))
    return render_template(
        "bharati/tinanta.html",
        q=q,
        dhatu_entry=dhatu_entry,
        prakriya=prakriya,
        short_history=short_history,
    )
