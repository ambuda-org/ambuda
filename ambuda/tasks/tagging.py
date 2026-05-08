"""Background tasks for batch tagging with Dharmamitra."""

import functools
import logging
import re
import time
from collections import deque
from typing import Any, TYPE_CHECKING
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DET
from sqlalchemy import select
from ambuda.utils.vidyut_shim import transliterate, Scheme

from ambuda import consts
from ambuda import database as db
from ambuda.tasks import app
from ambuda.tasks.utils import get_db_session
from ambuda.utils import revisions
from ambuda.utils import dharmamitra as dm_utils
from ambuda.utils.vidyut_loaders import get_kosha

if TYPE_CHECKING:
    from vidyut.kosha import Kosha


# Dharmamitra rate limit is 10 sentences per minute
DHARMAMITRA_MAX_QPS = 100 / 60.0


class RateLimiter:
    """Rate limiter for Dharmamitra API."""

    def __init__(self, qps: float):
        self.qps = qps
        self.start = time.time()
        self.count = 0

    @property
    def current_qps(self):
        now = time.time()
        duration = now - self.start
        return self.count / duration

    def tick(self):
        self.tick_by(1)

    def tick_by(self, n: int):
        self.count += n

    def wait(self):
        while self.current_qps > self.qps:
            time.sleep(1)


@functools.cache
def get_rate_limiter():
    return RateLimiter(DHARMAMITRA_MAX_QPS)


def to_plain_text_iast_sentences(blob: str) -> list[str]:
    blob = transliterate(blob, Scheme.Devanagari, Scheme.Iast)

    xml = ET.fromstring(blob)
    for el in xml.iter():
        if el.tag in {"sic", "note", "ref"}:
            el.text = ""
        el.tag = None
    clean_blob = ET.tostring(xml, encoding="unicode")
    clean_blob = re.sub("[0-9?!]", "", clean_blob)

    ret = []
    sentences = re.split(r"।|॥|\.", clean_blob)
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        ret.append(s)
    return ret


def _error(msg: str) -> dict:
    return {"status": "error", "error": msg}


def _tag_block_inner(
    app_env: str,
    text_slug: str,
    block_id: int,
    kosha: "Kosha",
) -> dict:
    from dharmamitra_sanskrit_grammar import DharmamitraSanskritProcessor as DSP

    def _block_error(reason):
        return {"status": "error", "reason": reason, "block_id": block_id}

    processor = DSP()
    limiter = get_rate_limiter()
    with get_db_session(app_env) as (session, query, config_obj):
        text = query.text(text_slug)
        if not text:
            return _block_error(f"Text {text_slug} not found.")

        bot_user = query.user(consts.BOT_USERNAME)
        if not bot_user:
            return _block_error('Bot user "{consts.BOT_USERNAME}" not found')

        block = session.execute(
            select(db.TextBlock).filter_by(id=block_id)
        ).scalar_one_or_none()
        if not block:
            return _block_error(f"Block {block_id} not found.")

        existing = session.execute(
            select(db.TokenBlock).filter_by(block_id=block_id)
        ).scalar_one_or_none()
        if existing and existing.version > 0:
            return {
                "status": "skipped",
                "block_id": block_id,
                "reason": "Block already has token data",
            }

        sentences_iast = to_plain_text_iast_sentences(block.xml)

        limiter.wait()
        results = processor.process_batch(
            sentences_iast,
            mode="unsandhied-lemma-morphosyntax",
            human_readable_tags=False,
        )
        limiter.tick_by(len(sentences_iast))

        if not results:
            return _block_error("No results from Dharmamitra.")

        try:
            resp = dm_utils.DharmamitraResponse.validate_python(results)
        except Exception as e:
            return _block_error(f"Could not parse Dharmamitra response: {e}")

        tsv_lines = []
        for sentence in resp:
            for token in sentence.grammatical_analysis:
                am_token = dm_utils.remap_token(token, kosha)
                form, base, parse = (am_token.form, am_token.base, am_token.parse)
                if form and base and parse:
                    tsv_lines.append(f"{form}\t{base}\t{parse}")

        if not tsv_lines:
            return {
                "status": "skipped",
                "block_id": block_id,
                "reason": "No valid tokens generated",
            }

        tsv_data = "\n".join(tsv_lines)

        token_block = session.execute(
            select(db.TokenBlock).filter_by(block_id=block_id)
        ).scalar_one_or_none()

        if not token_block:
            token_block = db.TokenBlock(
                text_id=text.id,
                block_id=block_id,
                version=0,
            )
            session.add(token_block)
            session.flush()

        try:
            new_version = revisions.add_token_revision(
                token_block=token_block,
                data=tsv_data,
                version=token_block.version,
                author_id=bot_user.id,
                block_id=block_id,
                session=session,
            )
            return {
                "status": "success",
                "block_id": block_id,
                "tokens": len(tsv_lines),
                "version": new_version,
            }
        except revisions.EditError as e:
            return _block_error(f"Edit conflict: {e}")


@app.task(bind=True)
def tag_text(
    self,
    app_env: str,
    text_slug: str,
):
    """Process all blocks in a text with rate limiting."""

    # Load one instance, use in all tasks.
    with get_db_session(app_env) as (session, query, config_obj):
        kosha = get_kosha(config_obj.VIDYUT_DATA_DIR)
        text = query.text(text_slug)
        if not text:
            return _error(f"Text {text_slug} not found")

        def iter_blocks():
            for section in text.sections:
                for block in section.blocks:
                    yield block

        rate_limiter = get_rate_limiter()
        blocks = list(iter_blocks())
        results: dict[str, Any] = {
            "status": "completed",
            "text_slug": text_slug,
            "total_blocks": len(blocks),
            "processed": 0,
            "success": 0,
            "skipped": 0,
            "errors": [],
        }

        for i, block in enumerate(blocks):
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": len(blocks),
                    "current_qps": rate_limiter.current_qps,
                },
            )

            try:
                resp = _tag_block_inner(app_env, text_slug, block.id, kosha)
            except Exception as e:
                logging.exception("Failed to tag %s/%s", text_slug, block.slug)
                resp = {"status": "error", "error": str(e)}

            results["processed"] += 1
            if resp["status"] == "success":
                logging.info(
                    "Tagged %s/%s (%d tokens)",
                    text_slug,
                    block.slug,
                    resp.get("tokens", 0),
                )
                results["success"] += 1
            elif resp["status"] == "skipped":
                results["skipped"] += 1
            elif resp["status"] == "error":
                results["errors"].append(
                    {
                        "block_id": block.id,
                        "error": resp.get("error", "Unknown error"),
                    }
                )

        return results
