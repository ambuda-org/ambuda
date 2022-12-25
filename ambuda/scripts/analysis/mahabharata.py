"""Add the Mahabharata parse data from DCS."""


from pathlib import Path
from typing import Iterator

import ambuda.scripts.analysis.dcs_utils as dcs
from ambuda.scripts.analysis.ramayana import get_kanda_and_sarga, map_and_write

TITLE_MAP = {
    "MBh, 1": "1",
    "MBh, 2": "2",
    "MBh, 3": "3",
    "MBh, 4": "4",
    "MBh, 5": "5",
    "MBh, 6": "6",
    "MBh, 7": "7",
    "MBh, 8": "8",
    "MBh, 9": "9",
    "MBh, 10": "10",
    "MBh, 11": "11",
    "MBh, 12": "12",
    "MBh, 13": "13",
    "MBh, 14": "14",
    "MBh, 15": "15",
    "MBh, 16": "16",
    "MBh, 17": "17",
    "MBh, 18": "18",
}


def iter_sections():
    text_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "dcs-raw"
        / "files"
        / "Mahābhārata"
    )
    for section_path in sorted(text_path.iterdir()):
        for section in dcs.parse_file(section_path):
            yield section


def iter_parsed_blocks() -> Iterator[tuple[str, str, str]]:
    for section in iter_sections():
        kanda, sarga = get_kanda_and_sarga(TITLE_MAP, section)
        for block in section.phrases:
            key = dcs.iast_to_slp1(block.raw)
            key = dcs.make_block_key(key)
            full_slug = f"{kanda}.{sarga}.{block.slug}"
            buf = []
            for token in block.tokens:
                buf.append("\t".join((token.form, token.lemma, token.parse)))
            yield key, full_slug, "\n".join(buf)


def run():
    map_and_write("mahabharatam", iter_parsed_blocks(), "M")


if __name__ == "__main__":
    run()
