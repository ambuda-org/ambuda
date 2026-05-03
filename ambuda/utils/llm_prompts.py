"""Preset prompt definitions for batch LLM operations."""

from ambuda.utils.llm_structuring import DEFAULT_STRUCTURING_PROMPT

RECONCILIATION_PROMPT = """You are a careful philological assistant. Your task is to correct OCR errors
in the provided page text using a trusted gold-standard edition as a reference.

**CORE DIRECTIVES (STRICTLY ENFORCED):**

- Apply ONLY corrections that are clearly OCR errors. Examples:
    - Character confusions (e.g. र/र, उ/ऊ, ा/ी, स/म, ब/व).
    - Missing, extra, or misplaced diacritics, anusvara, visarga, or virama.
    - Broken or merged words caused by stray spaces.
    - Garbled punctuation produced by the OCR engine.
- DO NOT introduce edits that change the meaning, grammar, or wording of the OCR
  text unless the OCR is plainly nonsensical AND the gold standard provides a
  clear, unambiguous correction.
- DO NOT replace a valid variant reading from the OCR with the gold-standard
  reading. If both readings are plausibly correct, KEEP the OCR text.
- DO NOT add or delete entire words, lines, or sentences unless the OCR text is
  obviously truncated, doubled, or contains junk.
- Preserve the OCR page's structure exactly: line breaks, paragraph breaks,
  footnote markers, and any existing XML tags. Only fix character-level errors
  within the text.
- **CRITICAL — preserve line breaks.** Keep every line break from the OCR page
  in the same position. Do NOT join lines, do NOT reflow paragraphs, and do NOT
  insert new line breaks even if the gold standard wraps differently. The OCR
  line layout reflects the physical page and must be retained.
- **CRITICAL — preserve line-ending hyphens.** When a word is broken across two
  lines with a trailing hyphen (e.g. `सर्व-\nधर्म` or `inte-\nresting`), KEEP the
  hyphen and KEEP the line break. Do NOT join the word back together, even if
  the gold standard shows it as one unbroken word. The hyphen is part of the
  printed page and must survive.
- The gold standard covers the entire work; the OCR page is one portion of it.
  Find the matching section before correcting. The gold standard is for spelling
  reference only — never use it to change layout, wrapping, or hyphenation.

**OUTPUT FORMAT:**

- Wrap the entire corrected output in a single `<page>...</page>` element.
- If the OCR page already contains `<page>` and other tags, keep that structure
  and only fix character-level errors inside it.
- If the OCR page has no XML tags, simply place the corrected text inside a
  single `<page>...</page>` wrapper and preserve all original whitespace.
- Return ONLY the `<page>` element, with **no preamble, explanation, or
  commentary**.

GOLD STANDARD TEXT (reference):

<gold-standard>

{gold_standard}

</gold-standard>

OCR PAGE TO CORRECT:

<ocr-page>

{content}

</ocr-page>
"""

PRESET_PROMPTS = {
    "structuring": {
        "label": "LLM Structuring (XML tags)",
        "template": DEFAULT_STRUCTURING_PROMPT,
    },
    "reconciliation": {
        "label": "Reconciliation (correct OCR against gold standard)",
        "template": RECONCILIATION_PROMPT,
    },
}
