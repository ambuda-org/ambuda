# API: https://cloud.google.com/vision/docs/fulltext-annotations
# Response format: https://cloud.google.com/vision/docs/reference/rest/v1/images/annotate#TextAnnotation
# Billing: https://console.cloud.google.com/billing/

import base64
import functools
import logging
from dataclasses import dataclass

import requests

from ambuda import database as db
from ambuda.utils import s3


_VISION_ANNOTATE_URL = "https://vision.googleapis.com/v1/images:annotate"

# Vision API request: 60s default is too tight for large images.
_HTTP_TIMEOUT_SECONDS = 120


@dataclass
class OcrResponse:
    #: A slightly sanitized version of the OCR's plain-text output.
    text_content: str
    #: Word-level bounding boxes stored as 5-tuples (x1, x2, y1, y2, text).
    bounding_boxes: list[tuple[int, int, int, int, str]]


def post_process(text: str) -> str:
    """Post process OCR text."""
    return (
        text
        # Danda and double danda
        .replace("||", "॥")
        .replace("|", "।")
        .replace("।।", "॥")
        # Remove curly quotes
        .replace("‘", "'")
        .replace("’", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


@functools.cache
def _get_credentials():
    """Return cached Google OAuth2 credentials.

    `google.auth.default()` honors GOOGLE_APPLICATION_CREDENTIALS, then falls
    back to gcloud user credentials and GCE metadata, matching the SDK lookup.
    """
    import google.auth

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    return creds


def _get_access_token() -> str:
    """Return a valid OAuth2 access token, refreshing if needed."""
    import google.auth.transport.requests

    creds = _get_credentials()
    if not creds.valid:
        creds.refresh(google.auth.transport.requests.Request())
    return creds.token


def _annotate(image_field: dict) -> dict:
    """Call Vision's images:annotate REST endpoint and return the first response."""
    body = {
        "requests": [
            {
                "image": image_field,
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    headers = {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }
    resp = requests.post(
        _VISION_ANNOTATE_URL,
        json=body,
        headers=headers,
        timeout=_HTTP_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("responses", [{}])[0]


def _build_image_field(
    page: db.Page, s3_bucket: str | None, cloudfront_base_url: str | None
) -> dict | None:
    """Build the `image` field of a Vision request: inline content or a URI."""
    if s3.is_local and s3_bucket:
        image_bytes = page.s3_path(s3_bucket).read_bytes()
        return {"content": base64.b64encode(image_bytes).decode("ascii")}
    if cloudfront_base_url:
        return {
            "source": {
                "imageUri": page.asset_url(s3_bucket, cloudfront_base_url),
            }
        }
    return None


# Vision REST returns detectedBreak.type as a string. Map to the same word/line
# logic the SDK-era code used (integer enum values 1..5).
_BREAK_SPACE = {"SPACE", "SURE_SPACE"}
_BREAK_EOL = "EOL_SURE_SPACE"
_BREAK_HYPHEN = "HYPHEN"
_BREAK_LINE = "LINE_BREAK"


def _extract_text_and_boxes(
    annotation: dict,
) -> tuple[str, list[tuple[int, int, int, int, str]]]:
    """Walk a fullTextAnnotation and produce (text, bounding_boxes)."""
    buf: list[str] = []
    bounding_boxes: list[tuple[int, int, int, int, str]] = []

    for vis_page in annotation.get("pages", []):
        for block in vis_page.get("blocks", []):
            for paragraph in block.get("paragraphs", []):
                for word in paragraph.get("words", []):
                    vertices = word.get("boundingBox", {}).get("vertices", [])
                    xs = [v.get("x", 0) for v in vertices]
                    ys = [v.get("y", 0) for v in vertices]
                    symbols = word.get("symbols", [])
                    word_text = "".join(s.get("text", "") for s in symbols)
                    if vertices:
                        bounding_boxes.append(
                            (min(xs), min(ys), max(xs), max(ys), word_text)
                        )

                    for sym in symbols:
                        buf.append(sym.get("text", ""))
                        break_type = (
                            sym.get("property", {})
                            .get("detectedBreak", {})
                            .get("type", "")
                        )
                        # End of word.
                        if break_type in _BREAK_SPACE:
                            buf.append(" ")
                        # End of line.
                        if break_type == _BREAK_EOL:
                            buf.append("\n")
                        # Hyphenated end-of-line.
                        elif break_type == _BREAK_HYPHEN:
                            buf.append("-\n")
                        # Clean end of region.
                        elif break_type == _BREAK_LINE:
                            buf.append("\n\n")

    return post_process("".join(buf)), bounding_boxes


def serialize_bounding_boxes(boxes: list[tuple[int, int, int, int, str]]) -> str:
    """Serialize a list of bounding boxes as a TSV."""
    return "\n".join("\t".join(str(x) for x in row) for row in boxes)


def run(
    page: db.Page, s3_bucket: str | None, cloudfront_base_url: str | None
) -> OcrResponse:
    """Run Google OCR over the given image.

    :return: an OCR response containing the image's text content and
        bounding boxes.
    """
    logging.debug(f"Starting full text annotation for page {page.id}")

    image_field = _build_image_field(page, s3_bucket, cloudfront_base_url)
    if image_field is None:
        return OcrResponse(text_content="", bounding_boxes=[])

    response = _annotate(image_field)
    annotation = response.get("fullTextAnnotation") or {}
    text_content, bounding_boxes = _extract_text_and_boxes(annotation)
    return OcrResponse(text_content=text_content, bounding_boxes=bounding_boxes)


def run_on_bytes(image_bytes: bytes) -> tuple[str, str | None]:
    """Run document OCR on raw image bytes.

    Returns ``(text, error_message)`` where exactly one is set. Used by the
    debug OCR-eval tool.
    """
    image_field = {"content": base64.b64encode(image_bytes).decode("ascii")}
    response = _annotate(image_field)
    err = response.get("error", {}).get("message")
    if err:
        return "", err
    annotation = response.get("fullTextAnnotation") or {}
    return annotation.get("text", "") or "", None
