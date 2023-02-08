import itertools
from dataclasses import dataclass
from ambuda.views.padmini.resources import get_ashtadhyayi, get_dhatupatha

from vidyut.prakriya import Dhatu, Purusha, Vacana, Lakara, Prayoga


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
class LakaraTable:
    name: str
    tinantas: list[list[list[str]]]


@dataclass
class DhatuPage:
    #: The dhatu this page corresponds to.
    dhatu: Dhatu
    lakaras: list[LakaraTable]


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
                cell.append(p.text)
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
