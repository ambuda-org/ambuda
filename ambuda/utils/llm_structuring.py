"""Utilities for LLM-based text structuring."""

GEMINI_MODEL = "gemini-3-flash-preview"


DEFAULT_STRUCTURING_PROMPT = """You are a highly specialized text structuring assistant. Your task
is to analyze the provided raw text page and add appropriate structural markup using specific XML
tags and attributes.

**CORE DIRECTIVES (STRICTLY ENFORCED):**

- Preserve the original text content exactly. Add only XML tags, attributes, and necessary whitespace.
    - Exception: you may delete clearly irrelevant text.
- Do not translate, modify, remove, or reorder any text content, including special characters.
- Return ONLY the structured XML text with **no preamble, explanation, or commentary**.
- If XML tags are present within the page text already, preserve them EXACTLY.

**I. DOCUMENT WRAPPER:**

- Wrap the entire output in the `<page>` tag.
- RULE: The page MUST be wrapped in `<page>...</page>` to form a valid document.

**II. BLOCK-LEVEL TAGS (direct children of <page>):**

Identify the function of each contiguous block of text and wrap it with the appropriate tag. If
necessary, you may split a block of text into multiple blocks by inserting newlines.

- Use <verse> for verses (typically numbered or metered lines)
- Use <p> for prose paragraphs (non-verse text).
- Use <heading> for section titles and chapter titles.
- Use <footnote> for blocks that start with a footnote marker, such as [^१] or [^1].
  Example: if a block starts with [^१], wrap it with <footnote name="१">...</footnote>.
- Use <ignore> for all other text content that does not ma

**III. INLINE TAGS** (direct children of block-level tags)

- Use <ref target="..." /> for inline footnotes.
  Example: if [^१.] appears in a verse or paragraph, convert it to <ref target="१." />.
  EXACTLY preserve the text in [^...] as the `target` attribute value.
- Use <stage> for stage directions. Wrap parentheses if present.
- Use <speaker> for speakers. Wrap dashes if present.
- Use <chaya> for Sanskrit translations of Prakrit text. Wrap brackets if present.

**IV. TAG ATTRIBUTES:**

- `merge-next`
  - Values: "true"
  - Add merge-next="true" if a block clearly continues onto the next page. Otherwise, leave
    the attribute unset.

TEXT TO STRUCTURE FOLLOWS:

<text-to-structure>

{content}

</text-to-structure>
"""


def run(
    content: str, api_key: str, prompt_template: str = DEFAULT_STRUCTURING_PROMPT
) -> str:
    if not content:
        raise ValueError("No content provided for structuring")

    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    from google import genai

    client = genai.Client(api_key=api_key)
    prompt = prompt_template.format(content=content)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)

    return response.text


PAGE_DELIMITER_START = "===PAGE_START {slug}==="
PAGE_DELIMITER_END = "===PAGE_END {slug}==="

BATCH_WRAPPER = """You will process multiple pages. Each page is delimited below
between ===PAGE_START <slug>=== and ===PAGE_END <slug>=== markers.

Apply the instructions to EACH page independently. Return a JSON object with a
single "pages" array. Each entry must have:
  - "slug": the page slug exactly as given in the delimiter
  - "content": the LLM output for that page

Return one entry per input page. Do NOT skip pages. Do NOT include any
explanation outside the JSON object.

INSTRUCTIONS:
{instructions}

PAGES TO PROCESS:
{pages}"""


_BATCH_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["slug", "content"],
            },
        }
    },
    "required": ["pages"],
}


_RESPONSE_SNIPPET_CHARS = 500

# Push to the model's documented ceiling. Gemini Flash-class models cap output
# at roughly 65k tokens regardless of the 1M input window, so the batched call
# has a real per-batch page limit driven by this number.
_MAX_OUTPUT_TOKENS = 65536


class BatchParseError(Exception):
    """Raised when Gemini's batch response is missing or unparseable.

    Carries a `snippet` and `finish_reason` so the failure surfaces enough
    diagnostic information to debug the underlying cause (truncation, safety
    filtering, schema violation, etc.).
    """

    def __init__(self, message: str, snippet: str = "", finish_reason: str = ""):
        super().__init__(message)
        self.snippet = snippet
        self.finish_reason = finish_reason


def _finish_reason(response) -> str:
    """Extract the finish_reason from a Gemini response, defensively."""
    try:
        candidate = response.candidates[0]
        reason = getattr(candidate, "finish_reason", None)
        return str(reason) if reason is not None else ""
    except (AttributeError, IndexError, TypeError):
        return ""


def run_batch(
    pages: dict[str, str],
    api_key: str,
    prompt_template: str = DEFAULT_STRUCTURING_PROMPT,
) -> dict[str, str]:
    """Run the LLM over multiple pages in a single API call.

    Args:
        pages: mapping of page slug to page content.
        api_key: Gemini API key.
        prompt_template: the per-page prompt template (must contain {content}).

    Returns:
        mapping of page slug to LLM output. Pages the model omits are absent
        from the result.

    Raises:
        BatchParseError: when Gemini returns no text or unparseable JSON.
    """
    if not pages:
        raise ValueError("No pages provided")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    # The template is written for a single page. Strip {content} for the
    # instructions block; the actual contents go into the delimited section.
    instructions = prompt_template.replace("{content}", "<page content appears here>")

    page_sections = []
    for slug, content in pages.items():
        page_sections.append(
            f"{PAGE_DELIMITER_START.format(slug=slug)}\n"
            f"{content}\n"
            f"{PAGE_DELIMITER_END.format(slug=slug)}"
        )

    prompt = BATCH_WRAPPER.format(
        instructions=instructions,
        pages="\n\n".join(page_sections),
    )

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_BATCH_RESPONSE_SCHEMA,
            # Push to the model's ceiling so we don't silently truncate large
            # batches. If the model still hits this cap, finish_reason will be
            # MAX_TOKENS and the user should run a smaller page range.
            max_output_tokens=_MAX_OUTPUT_TOKENS,
        ),
    )

    response_text = response.text or ""
    finish_reason = _finish_reason(response)

    if "MAX_TOKENS" in finish_reason:
        raise BatchParseError(
            "Gemini hit the output-token ceiling — the batch is too large. "
            "Try a smaller page range.",
            snippet=response_text[:_RESPONSE_SNIPPET_CHARS],
            finish_reason=finish_reason,
        )

    if not response_text:
        raise BatchParseError(
            f"Gemini returned an empty response (finish_reason={finish_reason or 'unknown'}). "
            "This is often caused by safety filtering or an empty candidate.",
            snippet="",
            finish_reason=finish_reason,
        )

    return _parse_batch_response(response_text, finish_reason)


def _parse_batch_response(
    response_text: str, finish_reason: str = ""
) -> dict[str, str]:
    """Parse Gemini's JSON output back into per-page results.

    Raises BatchParseError on unparseable JSON, including a snippet of the
    response so the caller can surface what actually came back.
    """
    import json

    snippet = response_text[:_RESPONSE_SNIPPET_CHARS]

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise BatchParseError(
            f"Gemini returned non-JSON output (finish_reason={finish_reason or 'unknown'}): {e}",
            snippet=snippet,
            finish_reason=finish_reason,
        ) from e

    if not isinstance(data, dict) or "pages" not in data:
        raise BatchParseError(
            f"Gemini response missing 'pages' key (finish_reason={finish_reason or 'unknown'}).",
            snippet=snippet,
            finish_reason=finish_reason,
        )

    results = {}
    for entry in data.get("pages", []):
        if not isinstance(entry, dict):
            continue
        slug = entry.get("slug")
        content = entry.get("content")
        if isinstance(slug, str) and isinstance(content, str):
            results[slug] = content
    return results
