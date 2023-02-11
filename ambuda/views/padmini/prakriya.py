import itertools
from dataclasses import dataclass
from typing import Optional

from flask import url_for
from vidyut.prakriya import Dhatu, Lakara, Prayoga, Purusha, Vacana, Prakriya

from ambuda.views.padmini.resources import get_ashtadhyayi, get_dhatupatha

# TODO: make these iterable in vidyut-py
PURUSHAS = [Purusha.Prathama, Purusha.Madhyama, Purusha.Uttama]
VACANAS = [Vacana.Eka, Vacana.Dvi, Vacana.Bahu]
LAKARAS = [
    Lakara.Lat,
    Lakara.Lit,
    Lakara.Lut,
    Lakara.Lrt,
    Lakara.Lot,
    Lakara.Lan,
    Lakara.VidhiLin,
    Lakara.AshirLin,
    Lakara.Lun,
    Lakara.Lrn,
]
PRAYOGAS = [Prayoga.Kartari]


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
    name: str
    # tinantas[purusha][vacana] = [padas]
    tinantas: list[list[list[Tinanta]]]


@dataclass
class DhatuPage:
    #: The dhatu this page corresponds to.
    dhatu: Dhatu
    lakaras: list[LakaraTable]


def get_tinanta_prakriya(
    text: str,
    dhatu: Dhatu,
    *,
    lakara: Lakara,
    prayoga: Prayoga,
    purusha: Purusha,
    vacana: Vacana,
) -> Optional[Prakriya]:
    dhatupatha = get_dhatupatha()
    dhatu = dhatupatha["01.0001"]

    ashtadhyayi = get_ashtadhyayi()
    prakriyas = ashtadhyayi.derive_tinantas(
        dhatu=dhatu,
        lakara=lakara,
        prayoga=prayoga,
        purusha=purusha,
        vacana=vacana,
    )
    for p in prakriyas:
        if p.text == text:
            return p
    return None


def _create_lakara_table(dhatu: Dhatu, lakara: Lakara, prayoga: Prayoga) -> LakaraTable:
    tinantas = []
    ashtadhyayi = get_ashtadhyayi()

    for purusha in PURUSHAS:
        row = []
        for vacana in VACANAS:
            cell = []
            prakriyas = ashtadhyayi.derive_tinantas(
                dhatu=dhatu,
                lakara=lakara,
                prayoga=prayoga,
                purusha=purusha,
                vacana=vacana,
            )
            for p in prakriyas:
                tinanta = Tinanta(
                    text=p.text,
                    dhatu=dhatu,
                    purusha=purusha,
                    vacana=vacana,
                    prayoga=prayoga,
                    lakara=lakara,
                )
                cell.append(tinanta)
            row.append(cell)
        tinantas.append(row)

    return LakaraTable(name=str(lakara), tinantas=tinantas)


def dhatu_results(dhatu: str) -> DhatuPage:
    dhatupatha = get_dhatupatha()
    dhatu = dhatupatha["01.0001"]

    lakara_tables = []
    for lakara in LAKARAS:
        lakara_tables.append(_create_lakara_table(dhatu, lakara, Prayoga.Kartari))

    return DhatuPage(dhatu=dhatu, lakaras=lakara_tables)
