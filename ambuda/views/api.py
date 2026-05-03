"""All API endpoints, registered under the /api prefix.

Previously, API routes were scattered across individual view modules that
imported this blueprint. They are now co-located here for discoverability.
"""

import dataclasses
from dataclasses import dataclass

import defusedxml.ElementTree as DET
from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from pydantic import BaseModel
from sqlalchemy import orm, select

from ambuda.utils.vidyut_shim import Scheme

from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.rate_limit import limiter
from ambuda.utils import google_ocr, llm_structuring, xml
from ambuda.utils import word_parses as parse_utils
from ambuda.utils.parse_alignment import align_text_with_parse
from ambuda.utils.project_structuring import ProofPage, split_plain_text_to_blocks
from ambuda.utils.revisions import EditError, add_revision
from ambuda.utils.xml_validation import validate_proofing_xml
from ambuda.views.proofing.decorators import p2_required

bp = Blueprint("api", __name__)


# ---------------------------------------------------------------------------
# Proofing
# ---------------------------------------------------------------------------


class AutoStructureRequest(BaseModel):
    """Request model for auto-structuring page content."""

    content: str
    match_stage: bool = False
    match_speaker: bool = False
    match_chaya: bool = False


@dataclass
class PageSaveResponse:
    ok: bool
    message: str
    new_version: int | None = None
    new_status: str | None = None
    conflict_content: str | None = None


@bp.route("/ocr/<project_slug>/<page_slug>/")
@limiter.limit("15/hour")
@login_required
def ocr_api(project_slug, page_slug):
    """Apply Google OCR to the given page."""
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)
    assert project_

    page_ = q.page(project_.id, page_slug)
    if not page_:
        abort(404)
    assert page_

    ocr_response = google_ocr.run(
        page_,
        current_app.config.get("S3_BUCKET"),
        current_app.config.get("CLOUDFRONT_BASE_URL"),
    )
    ocr_text = ocr_response.text_content

    structured_data = ProofPage.from_content_and_page_id(ocr_text, page_.id)
    ret = structured_data.to_xml_string()
    return ret


@bp.route("/llm-structuring/<project_slug>/<page_slug>/", methods=["POST"])
@limiter.limit("10/hour")
@p2_required
def llm_structuring_api(project_slug, page_slug):
    project_ = q.project(project_slug)
    if project_ is None:
        abort(404)
    assert project_

    page_ = q.page(project_.id, page_slug)
    if not page_:
        abort(404)
    assert page_

    content = request.json.get("content", "")
    if not content:
        return "Error: No content provided", 400

    try:
        api_key = current_app.config.get("GEMINI_API_KEY")
        if not api_key:
            current_app.logger.error("GEMINI_API_KEY not configured")
            return "Error: LLM service is not available", 500

        structured_content = llm_structuring.run(content, api_key)
        return structured_content
    except Exception as e:
        current_app.logger.error(f"LLM structuring failed: {e}")
        return "Error: LLM structuring failed", 500


@bp.route("/proofing/auto-structure", methods=["POST"])
@limiter.limit("60/hour")
@login_required
def auto_structure_api():
    """Apply auto-structuring heuristics to the page content."""
    if not request.json:
        return jsonify({"error": "No data provided"}), 400

    try:
        req = AutoStructureRequest.model_validate(request.json)
    except Exception as e:
        current_app.logger.warning(f"Invalid auto-structure request: {e}")
        return jsonify({"error": "Invalid request data"}), 400

    try:
        root = DET.fromstring(req.content)
        if root.tag != "page":
            return jsonify({"error": "Invalid XML: root tag must be 'page'"}), 400

        text = "".join(root.itertext())
        blocks = split_plain_text_to_blocks(
            text,
            match_stage=req.match_stage,
            match_speaker=req.match_speaker,
            match_chaya=req.match_chaya,
            ignore_non_devanagari=True,
        )
        page = ProofPage(id=0, blocks=blocks)
        xml_str = page.to_xml_string()
        return jsonify({"content": xml_str})

    except Exception as e:
        current_app.logger.error(f"Auto-structuring failed: {e}")
        return jsonify({"error": "Auto-structuring failed"}), 500


def _check_well_formed_text(text: str) -> dict:
    """Check a single block's text for well-formedness. Returns a result dict."""
    import re

    from ambuda.utils.text_validation import WellFormedText

    errors = []
    m = re.search(WellFormedText.RE_ILLEGAL, text)
    if m:
        errors.append(f"unexpected '{m.group(1)}'")
    for seq in WellFormedText.FORBIDDEN_SEQUENCES:
        if seq in text:
            errors.append(f"forbidden '{seq}'")

    return {"ok": len(errors) == 0, "errors": errors}


def _check_one_block(text: str, block_type: str, chandas, checker) -> dict:
    """Run all applicable checks on a single block. Returns a unified result."""
    text = text.strip()
    checks: dict = {}
    error_count = 0

    # Well-formed text check (skip for ignore/metadata)
    if block_type not in ("ignore", "metadata"):
        wft = _check_well_formed_text(text)
        checks["well_formed_text"] = wft
        if not wft["ok"]:
            error_count += len(wft["errors"])

    # Meter check (only for verse blocks)
    if block_type == "verse" and text and chandas is not None:
        meter_result = _check_one_verse(text, chandas, checker)
        checks["meter"] = meter_result
        if not meter_result["ok"]:
            error_count += 1

    ok = error_count == 0
    return {"ok": ok, "error_count": error_count, "checks": checks}


def _check_one_verse(text: str, chandas, checker) -> dict:
    """Check meter for a single verse. Returns a result dict."""
    from ambuda.utils.vidyut_shim import Scheme, transliterate

    from ambuda.utils.text_validation import MeterCheck

    text = text.strip()
    if not text:
        return {"ok": False, "scan": []}

    slp1 = transliterate(text, Scheme.Devanagari, Scheme.Slp1)

    if len(slp1) > MeterCheck._MAX_CLASSIFY_LEN:
        return {"ok": False, "scan": [], "error": "Verse too long"}

    try:
        match = chandas.classify(slp1)
    except BaseException as exc:
        current_app.logger.warning("Chandas error in meter-check API: %s", exc)
        return {"ok": False, "scan": [], "error": str(exc)}

    if match.padya:
        return {"ok": True, "meter": match.padya}

    if MeterCheck._is_shloka(match.aksharas):
        return {"ok": True, "meter": "Shloka"}

    if MeterCheck._is_tristubh(match.aksharas):
        return {"ok": True, "meter": "Trishtubh"}

    scan = [
        [
            {
                "text": transliterate(a.text, Scheme.Slp1, Scheme.Devanagari),
                "weight": a.weight,
            }
            for a in line_aksharas
        ]
        for line_aksharas in match.aksharas
    ]
    checker._mark_odd_aksharas(scan)
    return {"ok": False, "scan": scan}


@bp.route("/proofing/meter-check", methods=["POST"])
@login_required
def meter_check_api():
    """Check the meter of a batch of Devanagari verses.

    Accepts {"verses": ["...", ...]}. Returns {"results": [...]}.
    """
    from ambuda.utils.text_validation import MeterCheck, _get_chandas

    data = request.get_json()
    if not data or "verses" not in data:
        return jsonify({"error": "Missing 'verses' field"}), 400

    verses = data["verses"]
    if not isinstance(verses, list):
        return jsonify({"error": "'verses' must be an array"}), 400

    chandas = _get_chandas()
    checker = MeterCheck()
    results = [_check_one_verse(v, chandas, checker) for v in verses]
    return jsonify({"results": results})


@bp.route("/proofing/block-check", methods=["POST"])
@login_required
def block_check_api():
    """Check a batch of blocks for text well-formedness and meter.

    Accepts {"blocks": [{"text": "...", "type": "verse"}, ...]}.
    Returns {"results": [{"ok": true, "error_count": 0, "checks": {...}}, ...]}.
    """
    from ambuda.utils.text_validation import MeterCheck, _get_chandas

    data = request.get_json()
    if not data or "blocks" not in data:
        return jsonify({"error": "Missing 'blocks' field"}), 400

    blocks = data["blocks"]
    if not isinstance(blocks, list):
        return jsonify({"error": "'blocks' must be an array"}), 400

    # Only init chandas if at least one verse block is present
    has_verse = any(b.get("type") == "verse" for b in blocks)
    chandas = _get_chandas() if has_verse else None
    checker = MeterCheck() if has_verse else None

    results = [
        _check_one_block(b.get("text", ""), b.get("type", "p"), chandas, checker)
        for b in blocks
    ]
    return jsonify({"results": results})


@bp.route("/proofing/tags")
def proofing_tags_api():
    """Return all existing project tags."""
    session = q.get_session()
    tags = list(session.scalars(select(db.ProjectTag)).all())
    return jsonify({"tags": [{"id": t.id, "name": t.name} for t in tags]})


@bp.route("/proofing/projects/<slug>/tags", methods=["POST"])
@p2_required
def proofing_project_tags_api(slug):
    """Set the full tag list for a project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    data = request.get_json()
    if data is None or "tags" not in data:
        return jsonify({"error": "Missing 'tags' field"}), 400

    tag_names = data["tags"]
    if not isinstance(tag_names, list):
        return jsonify({"error": "'tags' must be an array"}), 400

    session = q.get_session()
    resolved_tags = []
    for name in tag_names:
        name = str(name).strip()
        if not name:
            continue
        tag = session.scalars(
            select(db.ProjectTag).filter(db.ProjectTag.name == name)
        ).first()
        if tag is None:
            tag = db.ProjectTag(name=name)
            session.add(tag)
            session.flush()
        resolved_tags.append(tag)

    project_.tags = resolved_tags
    session.commit()

    return jsonify(
        {
            "ok": True,
            "tags": [{"id": t.id, "name": t.name} for t in project_.tags],
        }
    )


@bp.route("/proofing/<project_slug>/<page_slug>/history")
def page_history_api(project_slug, page_slug):
    from ambuda.views.proofing.page import _get_page_context

    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        abort(404)

    assert ctx
    revisions = []
    for r in reversed(ctx.cur.revisions):
        revisions.append(
            {
                "id": r.id,
                "created": r.created.strftime("%Y-%m-%d %H:%M"),
                "author": r.author.username,
                "summary": r.summary or "",
                "status": r.status.name,
                "revision_url": url_for(
                    "proofing.page.revision",
                    project_slug=project_slug,
                    page_slug=page_slug,
                    revision_id=r.id,
                    _external=True,
                ),
                "author_url": url_for(
                    "user.summary", username=r.author.username, _external=True
                ),
            }
        )

    return jsonify({"revisions": revisions})


@bp.route("/proofing/<project_slug>/<page_slug>/page-data")
def page_data_api(project_slug, page_slug):
    """Return page data as JSON for SPA navigation."""
    from ambuda.views.proofing.page import _get_page_context, _get_page_data_dict

    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        abort(404)

    assert ctx
    data = _get_page_data_dict(ctx, ctx.project)
    data["canSaveDirectly"] = current_user.is_authenticated and current_user.is_p1
    return jsonify(data)


def _jsonify_response(resp: PageSaveResponse, status_code: int = 200):
    d = {k: v for k, v in dataclasses.asdict(resp).items() if v is not None}
    return jsonify(d), status_code


@bp.route("/proofing/<project_slug>/<page_slug>/save", methods=["POST"])
def page_save_api(project_slug, page_slug):
    """Save page edits via AJAX. Returns JSON response."""
    import uuid

    from ambuda.views.proofing.page import _get_page_context

    ctx = _get_page_context(project_slug, page_slug)
    if ctx is None:
        return _jsonify_response(
            PageSaveResponse(ok=False, message="Page not found."), 404
        )

    assert ctx
    cur = ctx.cur

    content = request.form.get("content", "")
    version = request.form.get("version", "")
    status = request.form.get("status", "")
    summary = request.form.get("summary", "")
    explanation = request.form.get("explanation", "")

    if not content:
        return _jsonify_response(
            PageSaveResponse(ok=False, message="Content is required.")
        )

    # Validate XML
    xml_errors = validate_proofing_xml(content)
    if xml_errors:
        messages = [e.message for e in xml_errors]
        return _jsonify_response(
            PageSaveResponse(ok=False, message="; ".join(messages))
        )

    can_save_directly = current_user.is_authenticated and current_user.is_p1

    if can_save_directly:
        cur_content = cur.revisions[-1].content if cur.revisions else None
        content_has_changed = cur_content != content
        status_has_changed = cur.status.name != status
        has_changed = content_has_changed or status_has_changed

        try:
            if has_changed:
                new_version = add_revision(
                    cur,
                    summary=summary,
                    content=content,
                    status=status,
                    version=int(version),
                    author_id=current_user.id,
                )
                return _jsonify_response(
                    PageSaveResponse(
                        ok=True,
                        message="Saved changes.",
                        new_version=new_version,
                        new_status=status,
                    )
                )
            else:
                return _jsonify_response(
                    PageSaveResponse(
                        ok=True,
                        message="Skipped save. (No changes made.)",
                        new_version=int(version),
                        new_status=status,
                    )
                )
        except EditError:
            conflict = cur.revisions[-1]
            return _jsonify_response(
                PageSaveResponse(
                    ok=False,
                    message="Edit conflict. Please incorporate the changes below:",
                    conflict_content=conflict.content,
                    new_version=cur.version,
                )
            )
    else:
        latest_revision = cur.revisions[-1] if cur.revisions else None
        if latest_revision is None:
            return _jsonify_response(
                PageSaveResponse(
                    ok=False,
                    message="Cannot suggest edits on a page with no revisions.",
                )
            )

        session = q.get_session()
        suggestion = db.Suggestion(
            project_id=ctx.project.id,
            page_id=cur.id,
            revision_id=latest_revision.id,
            user_id=current_user.id if current_user.is_authenticated else None,
            batch_id=str(uuid.uuid4()),
            content=content,
            explanation=explanation,
        )
        session.add(suggestion)
        session.commit()
        return _jsonify_response(
            PageSaveResponse(
                ok=True,
                message="Your suggestion has been submitted for review.",
                new_version=int(version),
                new_status=cur.status.name,
            )
        )


# ---------------------------------------------------------------------------
# Texts / Reader
# ---------------------------------------------------------------------------


@bp.route("/texts/<text_slug>/blocks/<block_slug>")
def block_htmx(text_slug, block_slug):
    text = q.text(text_slug)
    if text is None:
        abort(404)
    assert text

    block = q.block(text.id, block_slug)
    if not block:
        abort(404)
    assert block

    html_block = xml.transform_text_block(block.xml)
    return render_template(
        "htmx/text-block.html",
        slug=block.slug,
        html=html_block,
    )


@bp.route("/texts/<text_slug>/<section_slug>")
def reader_json(text_slug, section_slug):
    """Return section data as JSON."""
    from ambuda.views.texts import _build_section_data

    text_ = q.text(text_slug)
    if text_ is None:
        abort(404)
    assert text_

    data = _build_section_data(text_, section_slug)
    return jsonify(data)


@bp.route("/translations/<translation_slug>/<section_slug>")
def translation_blocks(translation_slug, section_slug):
    """Return translation block HTML keyed by source block slug."""
    translation_text = q.text(translation_slug)
    if translation_text is None or translation_text.parent_id is None:
        abort(404)

    source_text_id = translation_text.parent_id

    db_session = q.get_session()
    block_load = orm.selectinload(db.TextSection.blocks)
    children_load = block_load.selectinload(db.TextBlock.children)

    stmt = (
        select(db.TextSection)
        .filter_by(text_id=source_text_id, slug=section_slug)
        .options(block_load, children_load)
    )
    source_section = db_session.scalars(stmt).first()
    if source_section is None:
        return jsonify({})

    result = {}
    for block in source_section.blocks:
        matching = [c for c in block.children if c.text_id == translation_text.id]
        if matching:
            html_parts = [xml.transform_text_block(c.xml) for c in matching]
            result[block.slug] = "".join(html_parts)

    scheme = _scheme_from_session()
    if scheme != Scheme.Devanagari:
        for slug in result:
            result[slug] = xml.transliterate_html(
                result[slug], Scheme.Devanagari, scheme
            )

    return jsonify(result)


@bp.route("/bookmarks/toggle", methods=["POST"])
def toggle_bookmark():
    """Toggle a bookmark on a text block."""

    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    block_slug = data.get("block_slug")

    if not block_slug:
        return jsonify({"error": "block_slug is required"}), 400

    session = q.get_session()

    block = session.scalar(select(db.TextBlock).where(db.TextBlock.slug == block_slug))
    if not block:
        return jsonify({"error": "Block not found"}), 404

    existing_bookmark = session.scalar(
        select(db.TextBlockBookmark).where(
            db.TextBlockBookmark.user_id == current_user.id,
            db.TextBlockBookmark.block_id == block.id,
        )
    )

    if existing_bookmark:
        session.delete(existing_bookmark)
        session.commit()
        return jsonify({"bookmarked": False, "block_slug": block_slug})
    else:
        bookmark = db.TextBlockBookmark(
            user_id=current_user.id,
            block_id=block.id,
        )
        session.add(bookmark)
        session.commit()
        return jsonify({"bookmarked": True, "block_slug": block_slug})


# ---------------------------------------------------------------------------
# Dictionaries
# ---------------------------------------------------------------------------


@bp.route("/dictionaries/<list:sources>/<query>")
def entry_htmx(sources, query):
    from ambuda.views.dictionaries import _fetch_entries, _get_dictionary_data

    dictionaries = _get_dictionary_data()
    sources = [s for s in sources if s in dictionaries]
    if not sources:
        abort(404)

    entries = _fetch_entries(sources, query)
    result = render_template(
        "htmx/dictionary-results.html",
        query=query,
        entries=entries,
        dictionaries=dictionaries,
    )

    scheme = _scheme_from_param(request.args.get("script"))
    if scheme != Scheme.Devanagari:
        result = xml.transliterate_html(result, Scheme.Devanagari, scheme)
    return result


# ---------------------------------------------------------------------------
# Bharati (grammar / morphology)
# ---------------------------------------------------------------------------


@bp.route("/bharati/query/<query>")
def bharati_query(query):
    from ambuda.utils.vidyut_shim import Scheme, detect, transliterate

    from ambuda.views.bharati import _get_kosha_entries

    query = query.strip()
    input_scheme = detect(query) or Scheme.HarvardKyoto
    query = transliterate(query, input_scheme, Scheme.Slp1)

    entries = _get_kosha_entries(query)
    return render_template("htmx/bharati-query.html", query=query, entries=entries)


@bp.route("/bharati/grammar")
def bharati_grammar():
    """Return kosha entries filtered by form, lemma, and parse."""
    from ambuda.utils.vidyut_shim import Scheme, detect, transliterate

    from ambuda.views.bharati import (
        _filter_kosha_entries,
        _get_kosha_entries,
        _parse_en_parse,
    )

    form = request.args.get("form", "").strip()
    lemma = request.args.get("lemma", "").strip()
    parse = request.args.get("parse", "").strip()

    if not form:
        return render_template("htmx/bharati-grammar.html", entries=[])

    entries = _get_kosha_entries(form)

    lemma_scheme = detect(lemma) or Scheme.HarvardKyoto
    lemma_slp1 = transliterate(lemma, lemma_scheme, Scheme.Slp1)

    parse_info = _parse_en_parse(parse)
    filtered = _filter_kosha_entries(entries, lemma_slp1, parse_info)

    return render_template("htmx/bharati-grammar.html", entries=filtered)


@bp.route("/bharati/dhatu/<dhatu_spec>")
def bharati_dhatu_fragment(dhatu_spec):
    """Return an HTML fragment with dhatu conjugation tables."""
    from ambuda.utils.vidyut_shim import Scheme, detect, transliterate

    from ambuda.views.bharati import (
        _create_lakara_table,
        get_dhatu_entries,
    )
    from vidyut.prakriya import DhatuPada, Lakara, Prayoga

    input_scheme = detect(dhatu_spec) or Scheme.Slp1
    dhatu_key = transliterate(dhatu_spec, input_scheme, Scheme.Slp1)
    dhatu_key = dhatu_key.replace("^", "").replace("\\", "")

    dhatu_map = get_dhatu_entries()
    dhatu_entry = dhatu_map.get(dhatu_key)
    if not dhatu_entry:
        return "<p class='text-slate-400 text-sm'>No root data available.</p>"

    dhatu = dhatu_entry.dhatu
    tinantas = []
    for la in [
        Lakara.Lat,
        Lakara.Lit,
        Lakara.Lut,
        Lakara.Lrt,
        Lakara.Lot,
        Lakara.Lan,
        Lakara.VidhiLin,
        Lakara.AshirLin,
        Lakara.Lun,
    ]:
        lakara = []
        for pada in [DhatuPada.Parasmaipada, DhatuPada.Atmanepada]:
            lakara.append(
                _create_lakara_table(
                    dhatu, lakara=la, prayoga=Prayoga.Kartari, pada=pada
                )
            )
        tinantas.append(lakara)

    return render_template(
        "htmx/bharati-dhatu.html",
        dhatu_entry=dhatu_entry,
        tinantas=tinantas,
    )


@bp.route("/bharati/krt/<krt_value>")
def bharati_krt_fragment(krt_value):
    """Return an HTML fragment with krt suffix information."""
    from ambuda.utils.vidyut_shim import Scheme, transliterate

    from ambuda.views.bharati import KRT_ANUBANDHAS
    from vidyut.prakriya import Krt

    krt_slp = transliterate(krt_value, Scheme.Slp1, Scheme.Slp1)
    try:
        krt = Krt(krt_slp)
    except ValueError:
        return "<p class='text-slate-400 text-sm'>No suffix data available.</p>"

    anubandhas = krt.anubandhas()
    if "yu~" in krt_slp or "vu~" in krt_slp:
        anubandhas = [x for x in anubandhas if str(x) != "udit"]
    if "vi~" in krt_slp:
        anubandhas = [x for x in anubandhas if str(x) != "idit"]

    meanings = []
    for a in anubandhas:
        raw_messages = KRT_ANUBANDHAS.get(str(a), [("(no information found)", "--")])
        messages = []
        for message, code in raw_messages:
            message = message.replace("[[", "`").replace("]]", "`")
            fragments = message.split("`")
            buf = []
            for i, fragment in enumerate(fragments):
                if i % 2 == 0:
                    buf.append(fragment)
                else:
                    buf.append(transliterate(fragment, Scheme.Slp1, Scheme.Devanagari))
            message = "".join(buf)
            messages.append((message, code))
        meanings.append((a, messages))

    return render_template(
        "htmx/bharati-krt.html",
        krt=krt,
        meanings=meanings,
    )


# ---------------------------------------------------------------------------
# Parses
# ---------------------------------------------------------------------------


@bp.route("/parses/<text_slug>/<block_slug>")
def block_parse_htmx(text_slug, block_slug):
    text = q.text_meta(text_slug)
    if text is None:
        abort(404)

    block = q.block(text.id, block_slug)
    if block is None:
        abort(404)

    parse = q.block_parse(block.id)
    if not parse:
        abort(404)

    tokens = parse_utils.extract_tokens(parse.data)
    aligned = align_text_with_parse(block.xml, tokens)
    result = render_template(
        "htmx/parsed-tokens.html",
        text_slug=text_slug,
        block_slug=block_slug,
        aligned=aligned,
    )

    scheme = _scheme_from_session()
    result = xml.transliterate_html(result, Scheme.Devanagari, scheme)
    return result


def _scheme_from_session() -> Scheme:
    try:
        return Scheme.from_string(session.get("script", "Devanagari"))
    except ValueError:
        return Scheme.Devanagari


def _scheme_from_param(script_param: str | None) -> Scheme:
    if not script_param:
        return Scheme.Devanagari
    try:
        return Scheme.from_string(script_param)
    except ValueError:
        return Scheme.Devanagari
