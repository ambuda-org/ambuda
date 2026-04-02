"""Views for basic site pages."""

import re

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ambuda import queries as q
from ambuda.consts import LOCALES
from ambuda.utils import metadata_catalog
from ambuda.utils.vidyut_shim import transliterate, detect, Scheme

bp = Blueprint("site", __name__)


_NORM_MAP = {
    "ee": "i",
    "oo": "u",
    "ou": "au",
    "x": "ks",
    " ": "",
    "sh": "s",
    "z": "s",
    "kh": "k",
    "gh": "g",
    "ch": "c",
    "jh": "j",
    "Th": "T",
    "Dh": "D",
    "th": "t",
    "dh": "d",
    "ph": "p",
    "bh": "b",
    "RR": "R",
    "lR": "l",
    "G": "n",
    "J": "n",
    "M": "n",
    "m": "n",
}
_NORM_RE = re.compile("|".join(sorted(_NORM_MAP, key=lambda k: -len(k))))


def _normalize_hk(s: str) -> str:
    """Normalize a Harvard-Kyoto string for fuzzy matching (mirrors JS normalizeHK)."""
    return _NORM_RE.sub(lambda m: _NORM_MAP[m.group()], s)


def _to_hk(s: str) -> str:
    """Convert any-script input to Harvard-Kyoto."""
    scheme = detect(s)
    if scheme == Scheme.HarvardKyoto:
        return s
    return transliterate(s, scheme, Scheme.HarvardKyoto)


@bp.route("/")
def index():
    all_texts = metadata_catalog.create_text_entries()
    grouped_entries = metadata_catalog.create_grouped_text_entries(all_texts)
    recent_texts = metadata_catalog.create_recent_text_entries(all_texts)
    config = q.site_config()
    popular_slugs = config.popular_texts
    text_by_slug = {e.text.slug: e for e in all_texts}
    popular_texts = [text_by_slug[s] for s in popular_slugs if s in text_by_slug]
    return render_template(
        "index.html",
        grouped_entries=grouped_entries,
        recent_texts=recent_texts,
        popular_texts=popular_texts,
    )


@bp.route("/api/search-items")
def search_items():
    all_texts = metadata_catalog.create_text_entries()
    items = [
        {
            "title": transliterate(
                e.text.title, Scheme.HarvardKyoto, Scheme.Devanagari
            ),
            "iast": transliterate(e.text.title, Scheme.HarvardKyoto, Scheme.Iast),
            "slug": e.text.slug,
            "alternate_titles": [
                transliterate(a.title, Scheme.HarvardKyoto, Scheme.Devanagari)
                for a in e.text.alternate_titles
            ],
        }
        for e in all_texts
    ]
    resp = jsonify(items)
    resp.cache_control.public = True
    resp.cache_control.max_age = 3600
    return resp


@bp.route("/search")
def search():
    raw_query = request.args.get("q", "").strip()
    if not raw_query:
        return redirect(url_for("site.index"))

    q_norm = _normalize_hk(_to_hk(raw_query)).lower()
    all_texts = metadata_catalog.create_text_entries()
    results = []
    for entry in all_texts:
        title_norm = _normalize_hk(entry.text.title).lower()
        alt_norms = [
            _normalize_hk(a.title).lower() for a in entry.text.alternate_titles
        ]
        if q_norm in title_norm or any(q_norm in a for a in alt_norms):
            results.append(entry)

    return render_template(
        "search.html",
        query=raw_query,
        results=results,
    )


@bp.route("/contact")
def contact():
    return redirect(url_for("about.contact"))


@bp.route("/blog.xml")
def blog_feed():
    return redirect(url_for("blog.feed"))


@bp.route("/donate")
def donate():
    return render_template("site/donate.html")


@bp.route("/donate/<title>/<cost>")
def donate_for_project(title, cost):
    return render_template("site/donate-for-project.html", title=title, cost=cost)


@bp.route("/sponsor")
def sponsor():
    sponsorships = q.project_sponsorships()
    return render_template("site/sponsor.html", sponsorships=sponsorships)


@bp.route("/support")
def support():
    return render_template("site/support.html")


@bp.route("/test-sentry-500")
def sentry_500():
    """Sentry integration test. Should trigger a 500 error in prod."""
    _ = 1 / 0


@bp.app_errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@bp.app_errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404


@bp.app_errorhandler(413)
def request_too_large(e):
    return render_template("413.html"), 413


@bp.app_errorhandler(500)
def internal_server_error(e):
    return render_template("500.html"), 500


@bp.route("/script/<slug>")
def set_script(slug=None):
    session["script"] = slug
    return redirect(request.referrer or url_for("site.index"))


@bp.route("/language/<slug>")
def set_language(slug=None):
    locale = [L for L in LOCALES if slug == L.slug]
    if locale:
        locale = locale[0]
        session["locale"] = locale.code
    return redirect(url_for("site.index"))
