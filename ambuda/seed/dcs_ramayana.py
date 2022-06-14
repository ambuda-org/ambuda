from dataclasses import dataclass
from pathlib import Path

from indic_transliteration import sanscript
from sqlalchemy.orm import Session, load_only

import ambuda.database as db
import ambuda.seed.itihasa_utils as iti
from ambuda.seed.dcs_utils import get_parsed_rows


kanda_slug_map = {
    "Rām, Bā": "1",
    "Rām, Ay": "2",
    "Rām, Ār": "3",
    "Rām, Ki": "4",
    "Rām, Su": "5",
    "Rām, Yu": "6",
    "Rām, Utt": "7",
}


@dataclass
class ParsedBlock:
    slug: str
    rows: list


def iter_parsed_blocks():
    buf = []
    cur_slug = None
    text_path = (
        Path(__file__).parent.parent.parent / "dcs-parse-data" / "files" / "Rāmāyaṇa"
    )
    for section_path in sorted(text_path.iterdir()):
        for parse in get_parsed_rows(section_path):
            kanda_raw, _, sarga = parse.section_slug.rpartition(",")
            kanda = kanda_slug_map[kanda_raw]
            sarga = sarga.strip()
            slug = f"{kanda}.{sarga}.{parse.block_slug}"

            if slug != cur_slug:
                if buf:
                    yield ParsedBlock(slug=buf[0][0], rows=buf)
                buf = []
                cur_slug = slug
            buf.append([slug, parse.form, parse.lemma, parse.parse])
    if buf:
        yield ParsedBlock(slug=buf[0][0], rows=buf)


def create_parse_blob(pb: ParsedBlock) -> str:
    """Combine all of our structured parse data into an ugly blob.

    (We'll clean it up later!)
    """
    buf = []
    for slug, word, lemma, parse in pb.rows:
        word = sanscript.transliterate(word, sanscript.IAST, sanscript.SLP1)
        lemma = sanscript.transliterate(lemma, sanscript.IAST, sanscript.SLP1)
        buf.append("\t".join((word, lemma, parse)))
    return "\n".join(buf)


def block_metadata(session, text_id: int) -> dict[str, int]:
    blocks = (
        session.query(db.TextBlock)
        .filter_by(text_id=text_id)
        .options(
            load_only(
                db.TextBlock.id,
                db.TextBlock.slug,
            )
        )
        .all()
    )
    return {b.slug: b.id for b in blocks}


def run():
    print("Begin upload of parse data ...")

    engine = iti.create_db()
    with Session(engine) as session:
        text = session.query(db.Text).filter_by(slug="ramayanam").first()

        # Clear up old data
        print("Deleting old parse data ...")
        session.query(db.BlockParse).filter_by(text_id=text.id).delete()

        block_ids = block_metadata(session, text.id)
        for parsed_block in iter_parsed_blocks():
            try:
                block_id = block_ids[parsed_block.slug]
            except KeyError:
                print(f"Unknown block slug: {parsed_block.slug}")
            session.add(
                db.BlockParse(
                    text_id=text.id,
                    block_id=block_id,
                    data=create_parse_blob(parsed_block),
                )
            )

        print("Committing to database ...")
        session.commit()
    print("Done.")


if __name__ == "__main__":
    run()
