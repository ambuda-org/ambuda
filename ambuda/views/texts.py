"""Views related to texts: title pages, sections, verses, etc."""

import json
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    send_file,
    session,
    url_for,
)
from sqlalchemy import exists, orm, select

from ambuda.utils.vidyut_shim import transliterate, Scheme

import ambuda.database as db
import ambuda.queries as q
from ambuda.consts import SINGLE_SECTION_SLUG
from ambuda.models.texts import TextConfig
from ambuda.utils import s3
from ambuda.utils import metadata_catalog
from ambuda.utils import xml
from ambuda.utils.text_exports import ExportType
from ambuda.utils.metadata_catalog import (
    TextUrlsEntry,
    build_library_metadata,
    build_tei_headers_xml,
)
from ambuda.utils.json_serde import AmbudaJSONEncoder
from ambuda.utils.text_validation import ReportSummary
from ambuda.views.reader.schema import Block, Section

bp = Blueprint("texts", __name__)


def _prev_cur_next(sections: list[db.TextSection], slug: str):
    """Get the previous, current, and next sections.

    :param sections: all of the sections in this text.
    :param slug: the slug for the current section.
    """
    found = False
    i = 0
    for i, s in enumerate(sections):
        if s.slug == slug:
            found = True
            break

    if not found:
        raise ValueError(f"Unknown slug {slug}")

    prev = sections[i - 1] if i > 0 else None
    cur = sections[i]
    next = sections[i + 1] if i < len(sections) - 1 else None
    return prev, cur, next


def _make_section_url(text: db.Text, section: db.TextSection | None) -> str | None:
    if section:
        return url_for("texts.section", text_slug=text.slug, section_slug=section.slug)
    return None


def _page_url(page) -> str | None:
    if page:
        return url_for(
            "proofing.page.edit",
            project_slug=page.project.slug,
            page_slug=page.slug,
        )
    return None


def _build_section_data(text_: db.Text, section_slug: str) -> Section:
    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    db_session = q.get_session()

    block_load = orm.selectinload(db.TextSection.blocks)
    page_load = block_load.selectinload(db.TextBlock.page).selectinload(db.Page.project)
    parent_load = (
        block_load.selectinload(db.TextBlock.parents)
        .selectinload(db.TextBlock.page)
        .selectinload(db.Page.project)
    )
    stmt = (
        select(db.TextSection)
        .filter_by(text_id=text_.id, slug=section_slug)
        .options(block_load, page_load, parent_load)
    )
    cur = db_session.scalars(stmt).first()

    blocks = []
    for block in cur.blocks:
        # HACK: skip these for now.
        if block.xml.startswith("<title") or block.xml.startswith("<subtitle"):
            continue

        parent_blocks = None
        if text_.parent_id and block.parents:
            parent_blocks = [
                Block(
                    slug=pb.slug,
                    mula=xml.transform_text_block(pb.xml),
                    page_url=_page_url(pb.page),
                )
                for pb in block.parents
            ]

        blocks.append(
            Block(
                slug=block.slug,
                mula=xml.transform_text_block(block.xml),
                page_url=_page_url(block.page),
                parent_blocks=parent_blocks,
            )
        )

    scheme = _get_user_scheme()
    if scheme != Scheme.Devanagari:
        for block in blocks:
            block.mula = xml.transliterate_html(block.mula, Scheme.Devanagari, scheme)
            if block.parent_blocks:
                for pb in block.parent_blocks:
                    pb.mula = xml.transliterate_html(pb.mula, Scheme.Devanagari, scheme)

    return Section(
        text_title=transliterate(text_.title, Scheme.HarvardKyoto, scheme),
        section_title=_transliterate_slug(cur.title, scheme),
        section_slug=section_slug,
        blocks=blocks,
        prev_url=_make_section_url(text_, prev),
        next_url=_make_section_url(text_, next_),
    )


def _transliterate_slug(s: str, scheme: Scheme) -> str:
    return transliterate(s, Scheme.HarvardKyoto, scheme).replace("\u0964", ".")


def _get_user_scheme() -> Scheme:
    script_name = session.get("script", "Devanagari")
    try:
        return Scheme.from_string(script_name)
    except ValueError:
        return Scheme.Devanagari


def _export_key(x: db.TextExport) -> tuple:
    for i, ext in enumerate(("txt", "xml", "pdf", "csv")):
        if x.slug.endswith(ext):
            return (i, x.slug)
    return (4, x.slug)


@bp.route("/")
def index():
    """Show all texts."""
    grouped_entries = metadata_catalog.create_grouped_text_entries()
    all_texts = metadata_catalog.create_text_entries()
    search_items = [
        {
            "title": transliterate(
                e.text.title, Scheme.HarvardKyoto, Scheme.Devanagari
            ),
            "slug": e.text.slug,
            "alternate_titles": [
                transliterate(a.title, Scheme.HarvardKyoto, Scheme.Devanagari)
                for a in e.text.alternate_titles
            ],
        }
        for e in all_texts
    ]
    return render_template(
        "texts/index.html",
        grouped_entries=grouped_entries,
        search_items=search_items,
    )


@bp.route("/<slug>/")
def text(slug):
    """Show a text's title page and contents."""
    text_ = q.text(slug)
    if text_ is None:
        abort(404)
    assert text_

    if not text_.sections:
        abort(404)

    first_section_slug = text_.sections[0].slug
    return section(slug, first_section_slug)


@bp.route("/<slug>/about")
def text_about(slug):
    """Show a text's metadata."""
    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    header_data = xml.parse_tei_header(text.header)
    return render_template(
        "texts/text-about.html",
        text=text,
        header=header_data,
    )


@bp.route("/<slug>/resources")
def text_resources(slug):
    """Show a text's downloadable resources."""
    text = q.text(slug)
    if text is None:
        abort(404)
    assert text

    exports = sorted(text.exports, key=_export_key)
    return render_template("texts/text-resources.html", text=text, exports=exports)


@bp.route("/downloads/")
def downloads():
    """Show bulk download archives."""
    session = q.get_session()
    stmt = select(db.BulkExport).order_by(db.BulkExport.slug)
    bulk_exports = {e.export_type: e for e in session.scalars(stmt).all()}

    return render_template("texts/downloads.html", bulk_exports=bulk_exports)


def _export_urls(t: db.Text) -> TextUrlsEntry | None:
    """Build download URLs for a text's XML and plain-text exports."""
    xml_url = None
    text_url = None
    for export in t.exports:
        if export.export_type == ExportType.XML:
            xml_url = url_for(
                "texts.download_file", filename=export.slug, _external=True
            )
        elif export.export_type == ExportType.PLAIN_TEXT:
            text_url = url_for(
                "texts.download_file", filename=export.slug, _external=True
            )
    if xml_url or text_url:
        return TextUrlsEntry(xml=xml_url, text=text_url)
    return None


@bp.route("/downloads/metadata.json")
def metadata_json():
    """Return a JSON list of all texts with metadata."""
    all_colls = q.Query(q.get_session()).all_collections()
    data = build_library_metadata(
        texts=list(q.texts()),
        collections=all_colls,
        urls_fn=_export_urls,
    )
    return jsonify(data.model_dump())


@bp.route("/downloads/tei-headers.xml")
def tei_headers_xml():
    """Return a TEI corpus XML file containing all text headers."""
    xml_bytes = build_tei_headers_xml(list(q.texts()))
    return current_app.response_class(xml_bytes, mimetype="application/xml")


@bp.route("/downloads/<filename>")
def download_file(filename):
    base_url = current_app.config.get("CLOUDFRONT_BASE_URL")

    # Try per-text export first, then bulk export
    text_export = q.text_export(filename)
    if text_export:
        url = text_export.asset_url(base_url) if base_url else None
        if url:
            return redirect(url)

    session = q.get_session()
    bulk = session.scalars(select(db.BulkExport).filter_by(slug=filename)).first()
    if bulk:
        url = bulk.asset_url(base_url) if base_url else None
        if url:
            return redirect(url)

    # Local dev fallback: serve the file directly from the local S3 mock.
    s3_path_str = None
    if text_export:
        s3_path_str = text_export.s3_path
    elif bulk:
        s3_path_str = bulk.s3_path

    if s3_path_str and s3.is_local():
        s3_path = s3.S3Path.from_path(s3_path_str)
        local_path = (
            Path(s3.LocalFSBotoClient().base_path) / s3_path.bucket / s3_path.key
        )
        if local_path.exists():
            return send_file(local_path, as_attachment=True, download_name=filename)

    abort(404)


@bp.route("/<text_slug>/<section_slug>")
def section(text_slug, section_slug):
    """Show a specific section of a text."""
    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)
    assert text_

    try:
        prev, cur, next_ = _prev_cur_next(text_.sections, section_slug)
    except ValueError:
        abort(404)

    is_single_section_text = not prev and not next_
    if is_single_section_text:
        # Single-section texts have exactly one section whose slug should be
        # `SINGLE_SECTION_SLUG`. If the slug is anything else, abort.
        if section_slug != SINGLE_SECTION_SLUG:
            abort(404)

    db_session = q.get_session()
    has_no_parse = not db_session.scalar(
        select(exists().where(db.BlockParse.text_id == text_.id))
    )

    data = _build_section_data(text_, section_slug)
    json_payload = json.dumps(data, cls=AmbudaJSONEncoder)

    try:
        if isinstance(text_.config, str):
            config = TextConfig.model_validate_json(text_.config)
        elif isinstance(text_.config, dict):
            config = TextConfig.model_validate(text_.config)
        else:
            config = TextConfig()
    except Exception:
        config = TextConfig()

    prefix_titles = config.titles.fixed
    section_groups = {}
    for s in text_.sections:
        key, _, _ = s.slug.rpartition(".")
        if key not in section_groups:
            section_groups[key] = []
        name = s.slug
        if s.slug.count(".") == 1:
            x, y = s.slug.split(".")
            pattern = config.titles.patterns.get("x.y")
            if pattern:
                name = pattern.format(x=x, y=y)
        section_groups[key].append((s.slug, name))

    header_data = xml.parse_tei_header(text_.header)
    exports = sorted(text_.exports, key=_export_key)

    # Collect translations and commentaries from child texts.
    # A child whose language differs from the source is a translation;
    # one that shares the same language is a commentary.
    if text_.parent_id:
        siblings = [c for c in text_.parent.children if c.id != text_.id]
        source_lang = text_.parent.language
    else:
        siblings = list(text_.children)
        source_lang = text_.language

    translations = [c for c in siblings if c.language != source_lang]
    commentaries = [c for c in siblings if c.language == source_lang]

    report_summary = None
    raw_summary = q.text_report_summary(text_.id)
    if raw_summary:
        try:
            report_summary = ReportSummary.model_validate(raw_summary)
        except Exception:
            report_summary = None

    return render_template(
        "texts/reader.html",
        text=text_,
        prev=prev,
        section=cur,
        next=next_,
        json_payload=json_payload,
        html_blocks=data.blocks,
        has_no_parse=has_no_parse,
        is_single_section_text=is_single_section_text,
        section_groups=section_groups,
        prefix_titles=prefix_titles,
        text_about=header_data,
        raw_header=text_.header,
        exports=exports,
        translations=translations,
        commentaries=commentaries,
        report_summary=report_summary,
    )
