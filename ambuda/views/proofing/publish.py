"""Publishing routes for converting proofing projects into published texts."""

import dataclasses as dc
import difflib
import logging
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from lxml import etree
from xml.etree import ElementTree as ET

from ambuda.utils.slug import title_to_slug
from flask import (
    Blueprint,
    current_app,
    flash,
    render_template,
    request,
    url_for,
)
from flask_babel import lazy_gettext as _l
import sqlalchemy as sqla
from sqlalchemy.orm import selectinload
from werkzeug.exceptions import abort
from werkzeug.utils import redirect

import ambuda.utils.text_publishing as publishing_utils
from ambuda.consts import SINGLE_SECTION_SLUG
from ambuda.utils.text_publishing import Filter, TEIBlock, TEISection, filter_sort_key
from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.models.proofing import (
    LanguageCode,
    ProjectStatus,
    PublishConfig,
)
from ambuda.models.texts import TextStage, TextStatus
from ambuda.tasks.text_exports import upload_xml_export
from ambuda.utils import project_utils
from ambuda.utils.text_exports import read_cached_xml
from ambuda.views.proofing.decorators import p2_required
from flask_login import current_user


_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


def _resolve_publish_config(
    project_slug: str, text_slug: str
) -> tuple[db.Project, PublishConfig] | None:
    """Look up the project and its PublishConfig for *text_slug*.

    Returns ``(project, publish_config)`` on success.  On failure flashes
    an error message and returns ``None`` — the caller should redirect to
    the config page.
    """
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)

    session = q.get_session()
    pc = session.execute(
        sqla.select(PublishConfig)
        .join(db.Text, PublishConfig.text_id == db.Text.id)
        .where(
            PublishConfig.project_id == project_.id,
            db.Text.slug == text_slug,
        )
    ).scalar_one_or_none()

    if not pc:
        flash(f"No publish configuration found for text '{text_slug}'.", "error")
        return None

    return project_, pc


def _validate_slug(slug: str) -> str | None:
    if not slug:
        return "Slug is required."
    if not _SLUG_RE.match(slug):
        return (
            f"Invalid slug '{slug}': must contain only lowercase letters, digits, "
            "and hyphens; must start and end with a letter or digit."
        )
    if "--" in slug:
        return f"Invalid slug '{slug}': consecutive dashes are not allowed."
    return None


def _align_blocks(
    old_items: list, new_items: list
) -> list[tuple[int | None, int | None]]:
    """Align blocks based on ."""
    matcher = difflib.SequenceMatcher(a=old_items, b=new_items)
    pairs: list[tuple[int | None, int | None]] = []
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            for i, j in zip(range(a0, a1), range(b0, b1)):
                pairs.append((i, j))
        elif op == "replace":
            a_len = a1 - a0
            b_len = b1 - b0
            common = min(a_len, b_len)
            for k in range(common):
                pairs.append((a0 + k, b0 + k))
            for k in range(common, a_len):
                pairs.append((a0 + k, None))
            for k in range(common, b_len):
                pairs.append((None, b0 + k))
        elif op == "delete":
            for i in range(a0, a1):
                pairs.append((i, None))
        elif op == "insert":
            for j in range(b0, b1):
                pairs.append((None, j))
    return pairs


def _extract_header_from_tei(tei_path: Path) -> str:
    """Extract the ``<teiHeader>`` from a TEI file as a namespace-stripped XML string."""
    _ns = "{http://www.tei-c.org/ns/1.0}"
    for _, elem in etree.iterparse(str(tei_path), events=("end",)):
        if elem.tag == f"{_ns}teiHeader":
            for el in elem.iter():
                el.tag = etree.QName(el).localname
                for key in list(el.attrib):
                    if "{" in key:
                        el.attrib[etree.QName(key).localname] = el.attrib.pop(key)
            etree.cleanup_namespaces(elem)
            return etree.tostring(elem, encoding="unicode")
    return ""


def _build_tei_xml(
    header_xml: str,
    sections_data: list[tuple[str, list[tuple[str, str]]]],
    text_slug: str,
    language: str,
) -> str:
    """Build a pretty-printed TEI document from header and section/block data.

    We pretty-print so that we have a clean diff between old and new.
    """
    root = etree.Element("TEI")
    if header_xml:
        header_el = etree.fromstring(header_xml)
        root.append(header_el)
    text_el = etree.SubElement(root, "text")
    text_el.set("id", text_slug)
    text_el.set("lang", language)
    body = etree.SubElement(text_el, "body")
    for section_slug, blocks in sections_data:
        div = etree.SubElement(body, "div")
        div.set("n", section_slug)
        for block_slug, block_xml in blocks:
            block_el = etree.fromstring(block_xml)
            block_el.set("n", block_slug)
            div.append(block_el)
    etree.indent(root, space="  ")
    return etree.tostring(root, encoding="unicode", xml_declaration=False)


def _inline_highlight(old_line: str, new_line: str) -> str:
    """Return a single HTML string showing *old_line* → *new_line* inline.

    Unchanged text is passed through, deletions are wrapped in
    ``<del class="diff-hi-del">``, insertions in ``<ins class="diff-hi-add">``.
    """
    from markupsafe import escape

    sm = difflib.SequenceMatcher(None, old_line, new_line)
    parts: list[str] = []
    for op, a0, a1, b0, b1 in sm.get_opcodes():
        if op == "equal":
            parts.append(str(escape(old_line[a0:a1])))
        elif op == "replace":
            parts.append(f'<del class="diff-hi-del">{escape(old_line[a0:a1])}</del>')
            parts.append(f'<ins class="diff-hi-add">{escape(new_line[b0:b1])}</ins>')
        elif op == "delete":
            parts.append(f'<del class="diff-hi-del">{escape(old_line[a0:a1])}</del>')
        elif op == "insert":
            parts.append(f'<ins class="diff-hi-add">{escape(new_line[b0:b1])}</ins>')
    return "".join(parts)


def _build_diff_lines(old_xml: str, new_xml: str) -> list[dict]:
    """Produce a flat list of diff entries for a unified diff view.

    Each entry is a dict with ``"type"`` being one of:

    - ``"context"`` – unchanged line (has ``old_no``, ``new_no``, ``text``)
    - ``"add"`` – added line (has ``new_no``, ``text``)
    - ``"delete"`` – removed line (has ``old_no``, ``text``)
    - ``"replace"`` – changed line shown inline (has ``old_no``, ``new_no``,
      ``html`` with ``<del>``/``<ins>`` highlights)
    - ``"collapsed"`` – hidden unchanged section (has ``count``, ``lines``)

    For brand-new texts (empty *old_xml*), every line is an ``"add"`` entry
    with no collapsing.
    """
    CONTEXT_LINES = 3
    MIN_COLLAPSE = 4

    new_lines = new_xml.splitlines()

    if not old_xml:
        return [
            {"type": "add", "new_no": i + 1, "text": line}
            for i, line in enumerate(new_lines)
        ]

    old_lines = old_xml.splitlines()

    raw: list[dict] = []
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            for i, j in zip(range(a0, a1), range(b0, b1)):
                raw.append(
                    {
                        "type": "context",
                        "old_no": i + 1,
                        "new_no": j + 1,
                        "text": old_lines[i],
                    }
                )
        elif op == "replace":
            # Pair up old/new lines for inline highlighting.
            a_len, b_len = a1 - a0, b1 - b0
            common = min(a_len, b_len)
            for k in range(common):
                html = _inline_highlight(old_lines[a0 + k], new_lines[b0 + k])
                raw.append(
                    {
                        "type": "replace",
                        "old_no": a0 + k + 1,
                        "new_no": b0 + k + 1,
                        "html": html,
                    }
                )
            for i in range(a0 + common, a1):
                raw.append({"type": "delete", "old_no": i + 1, "text": old_lines[i]})
            for j in range(b0 + common, b1):
                raw.append({"type": "add", "new_no": j + 1, "text": new_lines[j]})
        elif op == "delete":
            for i in range(a0, a1):
                raw.append({"type": "delete", "old_no": i + 1, "text": old_lines[i]})
        elif op == "insert":
            for j in range(b0, b1):
                raw.append({"type": "add", "new_no": j + 1, "text": new_lines[j]})

    visible = [entry["type"] != "context" for entry in raw]
    for i, entry in enumerate(raw):
        if entry["type"] != "context":
            for j in range(max(0, i - CONTEXT_LINES), i):
                visible[j] = True
            for j in range(i + 1, min(len(raw), i + CONTEXT_LINES + 1)):
                visible[j] = True

    first_change = next(
        (i for i, e in enumerate(raw) if e["type"] != "context"), len(raw)
    )
    for i in range(first_change):
        visible[i] = False

    last_change = next(
        (i for i in range(len(raw) - 1, -1, -1) if raw[i]["type"] != "context"), -1
    )
    for i in range(last_change + 1, len(raw)):
        visible[i] = False

    result: list[dict] = []
    i = 0
    while i < len(raw):
        if visible[i]:
            result.append(raw[i])
            i += 1
        else:
            hidden: list[dict] = []
            while i < len(raw) and not visible[i]:
                hidden.append(raw[i])
                i += 1
            if len(hidden) >= MIN_COLLAPSE:
                result.append(
                    {"type": "collapsed", "count": len(hidden), "lines": hidden}
                )
            else:
                result.extend(hidden)

    return result


bp = Blueprint("publish", __name__)


PUBLISH_CONFIG_SCHEMA = {
    "properties": {
        "title": {"type": "string"},
        "slug": {"type": "string"},
        "target": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "author": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "language": {
            "$ref": "#/$defs/LanguageCode",
            "default": "sa",
        },
        "parent_slug": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "$defs": {
        "LanguageCode": {
            "type": "string",
            "enum": [c.value for c in LanguageCode],
        },
    },
    "required": ["slug", "title"],
}


@bp.route("/<slug>/publish", methods=["GET", "POST"])
@p2_required
def config(slug):
    """Configure publish settings for the project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    session = q.get_session()

    assert project_
    if request.method == "POST":
        import json

        publish_json = request.form.get("config", "")
        default = lambda: render_template(
            "proofing/projects/publish.html",
            project=project_,
            config=publish_json,
        )

        try:
            new_configs = json.loads(publish_json)
        except Exception as e:
            flash(f"Validation error: {e}", "error")
            return default()

        if not isinstance(new_configs, list):
            flash("Expected a list of publish configurations.", "error")
            return default()

        seen_ids: set = set()
        for pc in new_configs:
            pc_id = pc.get("id")
            if pc_id is None:
                continue
            if pc_id in seen_ids:
                flash(
                    f"Duplicate publish config id '{pc_id}' submitted. "
                    "Reload the page and try again.",
                    "error",
                )
                return redirect(url_for("proofing.publish.config", slug=slug))
            seen_ids.add(pc_id)

        for pc in new_configs:
            slug_error = _validate_slug(pc.get("slug", ""))
            if slug_error:
                flash(slug_error, "error")
                return default()

        for pc in new_configs:
            target = pc.get("target") or ""
            if target:
                try:
                    Filter(target)
                except ValueError as e:
                    flash(
                        f"Invalid filter for '{pc.get('slug', '')}': {e}",
                        "error",
                    )
                    return redirect(url_for("proofing.publish.config", slug=slug))

        # Load this project's existing configs once. We match new entries to
        # old ones by PublishConfig.id and update them in place; entries with
        # no matching id become new configs.
        old_pcs_by_id = {
            c.id: c
            for c in session.execute(
                sqla.select(PublishConfig)
                .where(PublishConfig.project_id == project_.id)
                .options(selectinload(PublishConfig.text))
            )
            .scalars()
            .all()
        }
        old_slugs_in_project = {c.text.slug for c in old_pcs_by_id.values() if c.text}
        referenced_ids = {
            pc.get("id") for pc in new_configs if pc.get("id") in old_pcs_by_id
        }
        # Stub texts whose slugs we'll free below. Public texts are left in place
        # but disconnected from the project (matches prior behavior).
        freed_text_ids = {
            c.text_id
            for cid, c in old_pcs_by_id.items()
            if cid not in referenced_ids and c.text and c.text.stage == TextStage.STUB
        }

        new_slugs = {pc.get("slug", "") for pc in new_configs}

        # Validate: new slugs must not collide with texts we don't already own
        # or aren't about to free.
        for pc in new_configs:
            pc_slug = pc.get("slug", "")
            if pc_slug in old_slugs_in_project:
                continue
            existing_text = session.execute(
                sqla.select(db.Text).where(db.Text.slug == pc_slug)
            ).scalar_one_or_none()
            if existing_text and existing_text.id not in freed_text_ids:
                flash(
                    f"A text with slug '{pc_slug}' already exists. "
                    "Please choose a different slug.",
                    "error",
                )
                return default()

        # Validate parent_slug references.
        for pc in new_configs:
            parent_slug = pc.get("parent_slug") or ""
            if parent_slug and parent_slug not in new_slugs:
                parent_text = session.execute(
                    sqla.select(db.Text).where(db.Text.slug == parent_slug)
                ).scalar_one_or_none()
                if not parent_text:
                    flash(
                        f"Parent slug '{parent_slug}' does not exist.",
                        "error",
                    )
                    return default()

        # Drop configs that weren't referenced. Stub texts are removed; public
        # texts are left in place.
        for cid, old_pc in old_pcs_by_id.items():
            if cid in referenced_ids:
                continue
            text = old_pc.text
            session.delete(old_pc)
            if text and text.stage == TextStage.STUB:
                session.delete(text)
        # Flush so freed slugs become available before we apply renames below.
        session.flush()

        # Upsert each config and its underlying Text.
        for pc in new_configs:
            pc_id = pc.get("id")
            pc_slug = pc.get("slug", "")
            pc_title = pc.get("title", "")
            pc_language = pc.get("language", "sa") or "sa"
            pc_author_name = pc.get("author") or None
            pc_target = pc.get("target") or None

            old_pc = old_pcs_by_id.get(pc_id) if pc_id else None
            if old_pc:
                config_obj = old_pc
                text = old_pc.text
                if text.slug != pc_slug:
                    text.slug = pc_slug
            else:
                # No matching id. Adopt an existing text with this slug if
                # there is one (e.g. a previously-published text being re-
                # attached); otherwise create a fresh stub.
                text = session.execute(
                    sqla.select(db.Text).where(db.Text.slug == pc_slug)
                ).scalar_one_or_none()
                if not text:
                    text = db.Text(
                        slug=pc_slug,
                        title=pc_title,
                        language=pc_language,
                        stage=TextStage.STUB,
                        project_id=project_.id,
                    )
                    session.add(text)
                    session.flush()
                config_obj = PublishConfig(
                    project_id=project_.id,
                    text_id=text.id,
                )
                session.add(config_obj)

            config_obj.target = pc_target
            text.title = pc_title
            text.language = pc_language
            text.project_id = project_.id

            # Sync author.
            if pc_author_name:
                author = session.execute(
                    sqla.select(db.Author).where(db.Author.name == pc_author_name)
                ).scalar_one_or_none()
                if not author:
                    author = db.Author(
                        name=pc_author_name, slug=title_to_slug(pc_author_name)
                    )
                    session.add(author)
                    session.flush()
                text.author_id = author.id
            else:
                text.author_id = None

            # Sync collections.
            collection_ids = pc.get("collection_ids") or []
            if collection_ids:
                colls = (
                    session.execute(
                        sqla.select(db.TextCollection).where(
                            db.TextCollection.id.in_(collection_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                text.collections = list(colls)
            else:
                text.collections = []

        session.flush()

        # Resolve parent_slug → parent_id now that all texts have their final slugs.
        for pc in new_configs:
            text = session.execute(
                sqla.select(db.Text).where(db.Text.slug == pc.get("slug", ""))
            ).scalar_one()
            parent_slug = pc.get("parent_slug") or ""
            if parent_slug:
                parent_text = session.execute(
                    sqla.select(db.Text).where(db.Text.slug == parent_slug)
                ).scalar_one_or_none()
                text.parent_id = parent_text.id if parent_text else None
            else:
                text.parent_id = None

        session.commit()
        flash("Configuration saved successfully.", "success")
        return redirect(url_for("proofing.publish.config", slug=slug))

    # GET: load existing configs from DB and sort by filter image range so
    # configs appear in manuscript order. Filters without an image selector
    # fall to the end and tiebreak by id (insertion order).
    configs = (
        session.execute(
            sqla.select(PublishConfig)
            .where(PublishConfig.project_id == project_.id)
            .order_by(PublishConfig.id)
            .options(
                selectinload(PublishConfig.text).selectinload(db.Text.collections),
                selectinload(PublishConfig.text).selectinload(db.Text.author),
            )
        )
        .scalars()
        .all()
    )
    configs = sorted(configs, key=lambda c: filter_sort_key(c.target))

    publish_config = [
        {
            "id": c.id,
            "slug": c.text.slug,
            "title": c.text.title,
            "target": c.target or "",
            "author": c.text.author.name if c.text.author else "",
            "language": c.text.language or "sa",
            "parent_slug": c.text.parent.slug if c.text.parent else "",
            "collection_ids": [coll.id for coll in c.text.collections],
            "_published": c.text.stage == TextStage.PUBLIC,
        }
        for c in configs
    ]

    config_schema = PUBLISH_CONFIG_SCHEMA

    # Get all authors for datalist
    authors = (
        session.execute(sqla.select(db.Author).order_by(db.Author.name)).scalars().all()
    )

    language_labels = {code.value: code.label for code in LanguageCode}

    all_collections = (
        session.execute(
            sqla.select(db.TextCollection).order_by(db.TextCollection.order)
        )
        .scalars()
        .all()
    )

    return render_template(
        "proofing/projects/publish.html",
        project=project_,
        publish_config=publish_config,
        publish_config_schema=config_schema,
        language_labels=language_labels,
        authors=authors,
        all_collections=all_collections,
    )


@bp.route("/<project_slug>/publish/<text_slug>/preview", methods=["GET"])
@p2_required
def preview(project_slug, text_slug):
    """Preview the changes that will be made when publishing a single text."""

    result = _resolve_publish_config(project_slug, text_slug)
    if result is None:
        return redirect(url_for("proofing.publish.config", slug=project_slug))
    project_, config = result

    warnings = []
    if not project_.print_title:
        warnings.append("No print title defined for this project.")
    if not project_.publisher:
        warnings.append("No publisher defined for this project.")
    if not project_.page_numbers:
        warnings.append("No page numbers defined for this project.")

    text = config.text

    # Generate new TEI and extract header + sections
    with tempfile.TemporaryDirectory() as tmpdir:
        tei_path = Path(tmpdir) / "preview.xml"
        document_data = publishing_utils.create_tei_document(project_, config, tei_path)

        # Strip namespaces for clean diffing
        root = etree.parse(str(tei_path)).getroot()
        for el in root.iter():
            el.tag = etree.QName(el).localname
            for key in list(el.attrib):
                if "{" in key:
                    el.attrib[etree.QName(key).localname] = el.attrib.pop(key)
        etree.cleanup_namespaces(root)
        new_xml = etree.tostring(root, encoding="unicode", xml_declaration=False)

    # Read old TEI from local file cache for diffing
    old_xml = ""
    if text.stage == TextStage.PUBLIC:
        cache_dir = current_app.config.get("SERVER_FILE_CACHE")
        raw_xml = read_cached_xml(cache_dir, text.slug)
        if raw_xml:
            try:
                old_root = etree.fromstring(raw_xml.encode())
                for el in old_root.iter():
                    el.tag = etree.QName(el).localname
                    for key in list(el.attrib):
                        if "{" in key:
                            el.attrib[etree.QName(key).localname] = el.attrib.pop(key)
                etree.cleanup_namespaces(old_root)
                old_xml = etree.tostring(
                    old_root, encoding="unicode", xml_declaration=False
                )
            except Exception:
                logging.exception("Failed to parse cached XML export for diff")

    diff_lines = _build_diff_lines(old_xml, new_xml)

    preview_data = {
        "slug": text.slug,
        "title": text.title,
        "target": config.target,
        "is_new": text.stage == TextStage.STUB,
        "diff_lines": diff_lines,
    }

    return render_template(
        "proofing/projects/publish-preview.html",
        project=project_,
        text_slug=text_slug,
        preview=preview_data,
        warnings=warnings,
    )


@bp.route("/<project_slug>/publish/<text_slug>/create", methods=["POST"])
@p2_required
def create(project_slug, text_slug):
    """Create or update texts based on the specified publish config."""

    result = _resolve_publish_config(project_slug, text_slug)
    if result is None:
        return redirect(url_for("proofing.publish.config", slug=project_slug))
    project_, config = result

    session = q.get_session()
    created_count = 0
    updated_count = 0
    texts_map = {}

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as fp:
        fp.close()
        tei_path = Path(fp.name)
        document_data = publishing_utils.create_tei_document(project_, config, tei_path)

        # Extract TEI header
        header = ""
        _ns = "{http://www.tei-c.org/ns/1.0}"
        for event, elem in etree.iterparse(fp.name, events=("end",)):
            if elem.tag == f"{_ns}teiHeader":
                for x in elem.getiterator():
                    x.tag = etree.QName(x).localname
                etree.cleanup_namespaces(elem)
                header = ET.tostring(elem, encoding="unicode")
                break

    task_dispatched = False
    try:
        # The text already exists (as a stub or previously published).
        text = config.text
        is_new_text = text.stage == TextStage.STUB

        text.header = header
        text.project_id = project_.id

        # Promote stub → public on first publish.
        if text.stage == TextStage.STUB:
            text.stage = TextStage.PUBLIC
            text.published_at = datetime.now(UTC)

        # Set an overall quality score for the text based on the quality of its source pages.
        #
        # TODO: make status more granular
        if SitePageStatus.R0.value in document_data.page_statuses:
            text.status = TextStatus.P0
        elif SitePageStatus.R1.value in document_data.page_statuses:
            text.status = TextStatus.P1
        else:
            text.status = TextStatus.P2

        # Create/update new blocks as necessary.
        #
        # NOTE: this must be done very carefully to avoid thrash during updates.
        existing_section_slugs: set[str] = {s.slug for s in text.sections}
        doc_sections = [s for s in document_data.items if isinstance(s, TEISection)]
        if not doc_sections:
            # For texts without section,s create "all" section to hold all blocks
            doc_sections = [
                TEISection(
                    slug=SINGLE_SECTION_SLUG,
                    blocks=[x for x in document_data.items if isinstance(x, TEIBlock)],
                )
            ]
        doc_section_slugs = {s.slug for s in doc_sections}
        section_map = {s.slug: s for s in text.sections}

        if existing_section_slugs != doc_section_slugs:
            new_sections = doc_section_slugs - existing_section_slugs
            old_sections = existing_section_slugs - doc_section_slugs

            for old_slug in old_sections:
                old_section = next(
                    (s for s in text.sections if s.slug == old_slug), None
                )
                if old_section:
                    session.delete(old_section)
                    del section_map[old_slug]

            for new_slug in new_sections:
                doc_section = next(
                    (s for s in doc_sections if s.slug == new_slug), None
                )
                if doc_section:
                    new_section = db.TextSection(
                        text_id=text.id,
                        slug=new_slug,
                        title=new_slug,
                    )
                    session.add(new_section)
                    section_map[new_slug] = new_section

            session.flush()

        for i, doc_section in enumerate(doc_sections):
            section = section_map[doc_section.slug]
            section.order = i

        existing_blocks_list = (
            session.execute(
                sqla.select(db.TextBlock)
                .where(db.TextBlock.text_id == text.id)
                .order_by(db.TextBlock.n)
            )
            .scalars()
            .all()
        )

        new_doc_blocks = []
        block_sections = []
        for doc_section in doc_sections:
            section = section_map[doc_section.slug]
            for block in doc_section.blocks:
                new_doc_blocks.append(block)
                block_sections.append(section)

        old_xmls = [b.xml for b in existing_blocks_list]
        new_xmls = [b.xml for b in new_doc_blocks]
        alignment = _align_blocks(old_xmls, new_xmls)

        block_index = 0
        for old_idx, new_idx in alignment:
            if old_idx is not None and new_idx is not None:
                block_index += 1
                existing_block = existing_blocks_list[old_idx]
                doc_block = new_doc_blocks[new_idx]
                existing_block.slug = doc_block.slug
                existing_block.xml = doc_block.xml
                existing_block.n = block_index
                existing_block.section_id = block_sections[new_idx].id
                existing_block.page_id = doc_block.page_id
            elif old_idx is not None:
                session.delete(existing_blocks_list[old_idx])
            else:
                block_index += 1
                doc_block = new_doc_blocks[new_idx]
                new_block = db.TextBlock(
                    text_id=text.id,
                    section_id=block_sections[new_idx].id,
                    slug=doc_block.slug,
                    xml=doc_block.xml,
                    n=block_index,
                    page_id=doc_block.page_id,
                )
                session.add(new_block)

        texts_map[text.slug] = text
        if is_new_text:
            created_count += 1
        else:
            updated_count += 1

        session.flush()

        # Special logic for translations and commentaries: align child blocks
        # to parent blocks. Parent_id is already set at config save time.
        if text.parent_id:
            parent_text = session.get(db.Text, text.parent_id)
            if parent_text:
                parent_blocks = (
                    session.execute(
                        sqla.select(db.TextBlock)
                        .where(db.TextBlock.text_id == parent_text.id)
                        .order_by(db.TextBlock.n)
                    )
                    .scalars()
                    .all()
                )

                child_blocks = (
                    session.execute(
                        sqla.select(db.TextBlock)
                        .where(db.TextBlock.text_id == text.id)
                        .order_by(db.TextBlock.n)
                    )
                    .scalars()
                    .all()
                )

                child_block_ids = [b.id for b in child_blocks]
                if child_block_ids:
                    session.execute(
                        sqla.delete(db.text_block_associations).where(
                            db.text_block_associations.c.child_id.in_(child_block_ids)
                        )
                    )

                parent_blocks_by_slug = {b.slug: b for b in parent_blocks}
                for child_block in child_blocks:
                    parent_block = parent_blocks_by_slug.get(child_block.slug)
                    if parent_block:
                        session.execute(
                            sqla.insert(db.text_block_associations).values(
                                parent_id=parent_block.id,
                                child_id=child_block.id,
                            )
                        )

        session.commit()

        # Upload the XML of this file to S3.
        upload_xml_export.apply_async(
            args=(
                text.id,
                text.slug,
                str(tei_path),
                current_app.config["AMBUDA_ENVIRONMENT"],
            ),
            headers={"initiated_by": current_user.username},
        )
        task_dispatched = True

        # Run quality report asynchronously.
        from ambuda.tasks.text_validation import run_report

        run_report.apply_async(
            args=(text.id, current_app.config["AMBUDA_ENVIRONMENT"]),
            headers={"initiated_by": current_user.username},
        )

        if created_count > 0:
            flash(f"Created text '{text.slug}'.", "success")
        if updated_count > 0:
            flash(f"Updated text '{text.slug}'.", "success")

        return redirect(url_for("proofing.publish.config", slug=project_slug))
    finally:
        if not task_dispatched:
            tei_path.unlink(missing_ok=True)
