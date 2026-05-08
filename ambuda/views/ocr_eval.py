"""OCR Eval debug tool: compare Google Vision and Sarvam.ai OCR results.

Localhost-only debug UI for uploading images, running OCR against both
providers, and viewing diffs. Results are stored in a separate SQLite database.
"""

import base64
import difflib
import json
import logging
import os
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

import requests
from flask import Blueprint, render_template, request, jsonify, current_app

bp = Blueprint("ocr_eval", __name__)

DB_PATH = Path("data/ocr_eval.db")

logger = logging.getLogger(__name__)


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ocr_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            google_text TEXT,
            sarvam_text TEXT,
            google_error TEXT,
            sarvam_error TEXT,
            google_time_ms INTEGER,
            sarvam_time_ms INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    return conn


def _run_google_ocr(image_bytes: bytes) -> tuple[str, str | None]:
    """Run Google Cloud Vision OCR on raw image bytes."""
    from ambuda.utils import google_ocr

    return google_ocr.run_on_bytes(image_bytes)


def _run_sarvam_ocr(image_bytes: bytes) -> tuple[str, str | None]:
    """Run Sarvam.ai OCR on raw image bytes."""
    import time

    api_key = os.environ.get("SARVAM_API_KEY")
    if not api_key:
        return "", "SARVAM_API_KEY not set"

    start = time.monotonic()
    b64 = base64.b64encode(image_bytes).decode("ascii")

    resp = requests.post(
        "https://api.sarvam.ai/ocr/process",
        headers={
            "Content-Type": "application/json",
            "API-Subscription-Key": api_key,
        },
        json={"image": f"data:image/png;base64,{b64}"},
        timeout=60,
    )
    elapsed_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code != 200:
        return "", f"HTTP {resp.status_code}: {resp.text[:500]}"

    data = resp.json()
    # Sarvam returns ocr_text or text field depending on API version
    text = data.get("ocr_text", "") or data.get("text", "") or ""
    return text, None


@bp.route("/")
def index():
    """Show upload form and recent runs."""
    db = _get_db()
    runs = db.execute(
        "SELECT * FROM ocr_runs ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    db.close()
    return render_template("debug/ocr_eval.html", runs=runs)


@bp.route("/run", methods=["POST"])
def run_ocr():
    """Upload an image, run both OCR engines, store and display results."""
    file = request.files.get("image")
    if not file or not file.filename:
        return "No image uploaded", 400

    image_bytes = file.read()
    filename = file.filename

    import time

    # Run Google OCR
    google_text, google_error = "", "Skipped"
    google_ms = 0
    try:
        t0 = time.monotonic()
        google_text, google_error = _run_google_ocr(image_bytes)
        google_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        google_error = str(e)
        logger.exception("Google OCR failed")

    # Run Sarvam OCR
    sarvam_text, sarvam_error = "", "Skipped"
    sarvam_ms = 0
    try:
        t0 = time.monotonic()
        sarvam_text, sarvam_error = _run_sarvam_ocr(image_bytes)
        sarvam_ms = int((time.monotonic() - t0) * 1000)
    except Exception as e:
        sarvam_error = str(e)
        logger.exception("Sarvam OCR failed")

    # Store in DB
    db = _get_db()
    cursor = db.execute(
        """INSERT INTO ocr_runs
           (filename, google_text, sarvam_text, google_error, sarvam_error,
            google_time_ms, sarvam_time_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            filename,
            google_text,
            sarvam_text,
            google_error,
            sarvam_error,
            google_ms,
            sarvam_ms,
        ),
    )
    run_id = cursor.lastrowid
    db.commit()
    db.close()

    return _render_run_detail(run_id)


@bp.route("/run/<int:run_id>")
def view_run(run_id: int):
    """View a specific run's results."""
    return _render_run_detail(run_id)


def _render_run_detail(run_id: int):
    db = _get_db()
    run = db.execute("SELECT * FROM ocr_runs WHERE id = ?", (run_id,)).fetchone()
    db.close()

    if not run:
        return "Run not found", 404

    # Generate unified diff
    google_lines = (run["google_text"] or "").splitlines(keepends=True)
    sarvam_lines = (run["sarvam_text"] or "").splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            google_lines,
            sarvam_lines,
            fromfile="Google Vision",
            tofile="Sarvam.ai",
            lineterm="",
        )
    )

    return render_template("debug/ocr_eval_detail.html", run=run, diff=diff)


@bp.route("/run/<int:run_id>/delete", methods=["POST"])
def delete_run(run_id: int):
    db = _get_db()
    db.execute("DELETE FROM ocr_runs WHERE id = ?", (run_id,))
    db.commit()
    db.close()
    return "", 204
