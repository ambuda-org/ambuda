"""Add parse data from DCS for a simple text."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from indic_transliteration import sanscript
from sqlalchemy.orm import Session

import ambuda.database as db
import ambuda.scripts.analysis.dcs_utils as dcs
from ambuda.seed.utils.itihasa_utils import create_db


def log(*a):
    print(*a)


def iter_sections(dcs_text_name):
    text_path = (
        Path(__file__).parent.parent.parent.parent
        / "data"
        / "dcs-raw"
        / "files"
        / f"{dcs_text_name}-all.conllu"
    )
    for section in dcs.parse_file(text_path):
        yield section


def iter_parsed_blocks(dcs_text_name) -> Iterator[tuple[str, str]]:
    for i, section in enumerate(iter_sections(dcs_text_name)):
        sarga = i + 1
        grouper = {}

        for phrase in section.phrases:
            full_slug = f"{sarga}.{phrase.slug}"
            if full_slug not in grouper:
                grouper[full_slug] = []

            tokens = grouper[full_slug]
            for token in phrase.tokens:
                tokens.append("\t".join((token.form, token.lemma, token.parse)))

        for slug, tokens in grouper.items():
            yield slug, "\n".join(tokens)


def _k(kv):
    try:
        return tuple(int(x) for x in kv[0].split("."))
    except ValueError:
        return (0, 0)


def get_block_slugs(text_slug: str) -> set[str]:
    engine = create_db()
    with Session(engine) as session:
        text = session.query(db.Text).filter_by(slug=text_slug).first()
        blocks = session.query(db.TextBlock).filter_by(text_id=text.id).all()
        return {b.slug for b in blocks}


def write(ambuda_text_slug: str, dcs_text_name: str, xml_id_for_text: str):
    text_slugs = get_block_slugs(ambuda_text_slug)
    num_hits = 0
    num_misses = 0

    with open(f"{ambuda_text_slug}.txt", "w") as f:
        for block_slug, parse_blob in iter_parsed_blocks(dcs_text_name):
            if block_slug in text_slugs:
                num_hits += 1
            else:
                num_misses += 1

            f.write(f"# id = {xml_id_for_text}.{block_slug}\n")
            f.write(parse_blob)
            f.write("\n\n")

    print(f"Done. ({num_hits} matches, {num_misses} mismatches.)")


def run():
    write(
        ambuda_text_slug="kumarasambhavam",
        dcs_text_name="Kumārasaṃbhava",
        xml_id_for_text="Ku",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract parse data.")
    parser.add_argument("--ambuda-slug", required=True)
    parser.add_argument("--dcs-name", required=True)
    parser.add_argument("--xml-id", required=True)

    args = parser.parse_args()
    write(
        ambuda_text_slug=args.ambuda_slug,
        dcs_text_name=args.dcs_name,
        xml_id_for_text=args.xml_id,
    )
