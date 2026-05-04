"""Diff-based safety net for reconciliation LLM output.

The reconciliation prompt instructs the LLM to preserve the OCR page's line
layout and trailing hyphens. This check catches *bulk* violations of that rule
(e.g. wholesale paragraph reflow, mass de-hyphenation) without rejecting the
small adjustments the LLM may legitimately need to make on garbled OCR — like
splitting a merged column into two lines or dropping a single spurious
page-edge hyphen.

A change is flagged only when it is large in BOTH absolute and relative terms.

XML wrapper tags around the page are stripped before comparison so the LLM
can add them without tripping the check.
"""

import re

_PAGE_WRAPPER_RE = re.compile(r"^\s*<page[^>]*>\s*|\s*</page>\s*$", re.DOTALL)

# Match an ASCII hyphen, devanagari hyphen-equivalents, or unicode hyphen at the
# very end of a line (allowing trailing whitespace).
_TRAILING_HYPHEN_RE = re.compile(r"[-‐‑‒–—]\s*$")

# Thresholds — flag only when both the absolute and the relative threshold are
# exceeded. Lets small corrections through; catches dramatic restructuring.
_LINE_COUNT_ABS_THRESHOLD = 5
_LINE_COUNT_FRACTION_THRESHOLD = 0.20
_HYPHEN_REMOVED_ABS_THRESHOLD = 3
_HYPHEN_REMOVED_FRACTION_THRESHOLD = 0.50


def _strip_page_wrapper(text: str) -> str:
    return _PAGE_WRAPPER_RE.sub("", text)


def _line_count(text: str) -> int:
    return len(text.splitlines())


def _hyphenated_lines(text: str) -> dict[int, str]:
    """Return {line_index: line_text} for every line ending with a dash."""
    return {
        i: line
        for i, line in enumerate(text.splitlines())
        if _TRAILING_HYPHEN_RE.search(line)
    }


_LINE_TAIL_CHARS = 30


def _tail(line: str) -> str:
    """Last few characters of a line, for diagnostic display."""
    line = line.rstrip()
    if len(line) <= _LINE_TAIL_CHARS:
        return line
    return "…" + line[-_LINE_TAIL_CHARS:]


def check_layout_preserved(ocr: str, output: str) -> list[str]:
    """Return a list of human-readable problems, or [] if layout is sufficiently preserved.

    Tolerates small adjustments — only bulk violations are flagged.
    """
    problems = []

    ocr_body = _strip_page_wrapper(ocr)
    out_body = _strip_page_wrapper(output)

    ocr_lines = _line_count(ocr_body)
    out_lines = _line_count(out_body)
    line_delta = abs(ocr_lines - out_lines)
    line_fraction = line_delta / ocr_lines if ocr_lines else 0
    if (
        line_delta >= _LINE_COUNT_ABS_THRESHOLD
        and line_fraction >= _LINE_COUNT_FRACTION_THRESHOLD
    ):
        problems.append(
            f"Line count changed substantially: {ocr_lines} → {out_lines} "
            f"({line_fraction:.0%} delta)."
        )

    ocr_hyphens = _hyphenated_lines(ocr_body)
    out_hyphens = _hyphenated_lines(out_body)
    missing = {i: ocr_hyphens[i] for i in ocr_hyphens.keys() - out_hyphens.keys()}
    missing_fraction = len(missing) / len(ocr_hyphens) if ocr_hyphens else 0
    if (
        len(missing) >= _HYPHEN_REMOVED_ABS_THRESHOLD
        and missing_fraction >= _HYPHEN_REMOVED_FRACTION_THRESHOLD
    ):
        # Show up to 5 affected lines so the user can see what kind of dashes
        # the model is dropping (word-break, dialogue, section markers, etc.).
        sample = sorted(missing.items())[:5]
        examples = "; ".join(f"L{i + 1}: {_tail(line)!r}" for i, line in sample)
        more = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
        problems.append(
            f"Trailing hyphens removed in bulk: "
            f"{len(missing)} of {len(ocr_hyphens)} ({missing_fraction:.0%}) gone. "
            f"Examples — {examples}{more}"
        )

    return problems
