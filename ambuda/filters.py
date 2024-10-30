"""Manages various small template filters."""

from datetime import datetime, UTC

from dateutil.relativedelta import relativedelta
from indic_transliteration import sanscript
from markdown_it import MarkdownIt

from ambuda.models.utils import utc_now

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
    return sanscript.transliterate(s, sanscript.SLP1, sanscript.DEVANAGARI)


def devanagari(s: str) -> str:
    """HK to Devanagari."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.DEVANAGARI)


def roman(s: str) -> str:
    """HK to Roman."""
    return sanscript.transliterate(s, sanscript.HK, sanscript.IAST)


def time_ago(dt: datetime, now=None) -> str:
    """Print a datetime relative to right now.

    :param dt: the datetime to check
    :param now: the "now" datetime. If not set, use `utc_now()`.

    """
    # FIXME: add i18n support
    now = now or utc_now()
    rd = relativedelta(now, dt.replace(tzinfo=UTC))
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
