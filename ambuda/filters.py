"""Manages various small template filters."""

from datetime import datetime

from dateutil.relativedelta import relativedelta
from vidyut.lipi import transliterate, Scheme
from markdown_it import MarkdownIt

#: A markdown parser for user-generated text.
#:
#: - `js-default` is like Commonmark but it disables raw HTML.
#: - `typographer` enables specific typography improvements:
#:   - `replacements` replaces `---` with `&mdash;`, etc.
#:   - `smartquotes` replaces basic quotes with opening and closing quotes.
#:   - `linkify` converts URLs like `"github.com"` into clickable links.
#:
#: Docs: https://markdown-it-py.readthedocs.io/en/latest/using.html
MARKDOWN = MarkdownIt("js-default", {"typographer": True, "linkify": True}).enable(
    ["replacements", "smartquotes", "linkify"]
)


def slp_to_devanagari(s: str) -> str:
    """SLP1 to Devanagari."""
    return transliterate(s, Scheme.Slp1, Scheme.Devanagari)


def devanagari(s: str) -> str:
    """HK to Devanagari."""
    return transliterate(s, Scheme.HarvardKyoto, Scheme.Devanagari)


def roman(s: str) -> str:
    """HK to Roman."""
    return transliterate(s, Scheme.HarvardKyoto, Scheme.Iast)


def time_ago(dt: datetime, now=None) -> str:
    """Print a datetime relative to right now.

    :param dt: the datetime to check
    :param now: the "now" datetime. If not set, use `utcnow()`.

    """
    # FIXME: add i18n support
    now = now or datetime.utcnow()
    rd = relativedelta(now, dt)
    for name in ["years", "months", "days", "hours", "minutes", "seconds"]:
        n = getattr(rd, name)
        if n:
            if n == 1:
                name = name[:-1]
            return f"{n} {name} ago"
    return "now"


def markdown(text: str) -> str:
    """Render the given Markdown text as HTML."""
    return MARKDOWN.render(text)
