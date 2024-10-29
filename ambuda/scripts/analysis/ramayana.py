"""Add the Ramayana parse data from DCS."""

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from indic_transliteration import sanscript
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.scripts.analysis.dcs_utils as dcs
from ambuda.seed.utils.data_utils import create_db

TITLE_MAP = {
    "Rām, Bā": "1",
    "Rām, Ay": "2",
    "Rām, Ār": "3",
    "Rām, Ki": "4",
    "Rām, Su": "5",
    "Rām, Yu": "6",
    "Rām, Utt": "7",
}


def get_kanda_and_sarga(kanda_slug_map, section: dcs.Section) -> tuple[str, str]:
    kanda_raw, _, sarga = section.slug.rpartition(",")
    kanda = kanda_slug_map[kanda_raw]
    return kanda.strip(), sarga.strip()


def iter_sections():
    text_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "dcs-raw"
        / "files"
        / "Rāmāyaṇa"
    )
    for section_path in sorted(text_path.iterdir()):
        yield from dcs.parse_file(section_path)


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


def map_keys_to_slugs(text_slug):
    key_to_slug = {}

    engine = create_db()
    with Session(engine) as session:
        text = session.query(db.Text).filter_by(slug=text_slug).first()
        blocks = session.query(db.TextBlock).filter_by(text_id=text.id).all()
        for b in blocks:
            for line in ET.fromstring(b.xml).iter("l"):
                raw_text = "".join(line.itertext())
                raw_text = sanscript.transliterate(
                    raw_text, sanscript.DEVANAGARI, sanscript.SLP1
                )
                block_key = dcs.make_block_key(raw_text)
                key_to_slug.setdefault(block_key, []).append(b.slug)

    assert key_to_slug
    return key_to_slug


def _k(kv):
    try:
        return tuple(int(x) for x in kv[0].split("."))
    except ValueError:
        return (0, 0, 0)


def map_and_write(text_slug, blocks_iter, xml_id_for_text):
    print("Mapping source text to slugs ...")
    key_to_slug = map_keys_to_slugs(text_slug)

    # Groups half-blocks with the same slug. These will be printed as one block.
    hits = {}
    misses = {}

    for key, dcs_slug, blob in blocks_iter:
        prefix, _, _ = dcs_slug.rpartition(".")
        if key in key_to_slug:
            candidates = key_to_slug[key]
            for i, c in enumerate(candidates):
                if c.startswith(prefix):
                    hits.setdefault(c, []).append(blob)
                    candidates.pop(i)
                    break
        else:
            misses.setdefault(dcs_slug, []).append((key, blob))
    print(f"{len(hits)} hits, {len(misses)} misses")

    print("Writing hits ...")
    with open(f"{text_slug}.txt", "w") as f:
        for slug, blobs in dict(sorted(hits.items(), key=_k)).items():
            f.write(f"# id = {xml_id_for_text}.{slug}\n")
            for blob in blobs:
                f.write(blob)
                f.write("\n")
            f.write("\n")

    print("Writing misses ...")
    with open(f"{text_slug}-errors.txt", "w") as f:
        for slug, keys_and_blobs in dict(sorted(misses.items(), key=_k)).items():
            for key, blob in keys_and_blobs:
                f.write(f"# dcs_id = {slug}\n")
                f.write(f"# key = {key}\n")
                f.write(blob)
                f.write("\n\n")
    print("Done.")


def run():
    map_and_write("ramayanam", iter_parsed_blocks(), "R")


if __name__ == "__main__":
    run()
