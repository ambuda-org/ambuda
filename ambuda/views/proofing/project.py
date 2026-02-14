import dataclasses as dc
import json
import logging
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import sqlalchemy as sqla
from celery import chain
from celery.result import GroupResult
from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    make_response,
    render_template,
    request,
    url_for,
)
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from markupsafe import Markup, escape
from pydantic import BaseModel, TypeAdapter
from sqlalchemy import orm, select
from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from wtforms import (
    FileField,
    RadioField,
    SelectField,
    StringField,
)
from wtforms.validators import DataRequired, ValidationError
from wtforms.widgets import TextArea
from wtforms_sqlalchemy.fields import QuerySelectField

from ambuda import database as db
from ambuda import queries as q
from ambuda.enums import SitePageStatus
from ambuda.models.proofing import ProjectSource, ProjectStatus
from ambuda.rate_limit import limiter
from ambuda.tasks import app as celery_app
from ambuda.tasks import batch_llm as batch_llm_tasks
from ambuda.tasks import llm_structuring as llm_structuring_tasks
from ambuda.tasks import ocr as ocr_tasks
from ambuda.tasks import projects as project_tasks
from ambuda.utils import project_structuring, project_utils
from ambuda.utils.llm_prompts import PRESET_PROMPTS
from ambuda.utils.project_structuring import ProofBlock, ProofPage, ProofProject
from ambuda.utils.revisions import add_revision
from ambuda.views.proofing.decorators import moderator_required, p2_required
from ambuda.views.proofing.main import (
    _is_allowed_document_file,
    _required_if_url,
    _required_if_local,
)
from ambuda.views.proofing.stats import calculate_stats

bp = Blueprint("project", __name__)
LOG = logging.getLogger(__name__)


@dc.dataclass
class BlockType:
    tag: str
    label: str


@dc.dataclass
class Language:
    code: str
    label: str


BLOCK_TYPES = [
    BlockType("p", "paragraph"),
    BlockType("verse", "verse"),
    BlockType("heading", "heading"),
    BlockType("title", "title"),
    BlockType("subtitle", "subtitle"),
    BlockType("footnote", "footnote"),
    BlockType("trailer", "trailer"),
    BlockType("ignore", "ignore"),
]

LANGUAGES = [
    Language(code="sa", label="Sanskrit"),
    Language(code="hi", label="Hindi"),
    Language(code="en", label="English"),
]


def _is_valid_page_number_spec(_, field):
    try:
        _ = project_utils.parse_page_number_spec(field.data)
    except Exception as e:
        raise ValidationError("The page number spec isn't valid.") from e


def _is_valid_slug(_, field):
    if not re.match(r"[a-zA-Z0-9-]+$", field.data):
        raise ValidationError("Invalid slug (should be alphanumeric or '-')")


class EditMetadataForm(FlaskForm):
    slug = StringField(
        _l("Slug"),
        render_kw={
            "placeholder": _l("e.g. avantisundarikatha"),
        },
        validators=[DataRequired(), _is_valid_slug],
    )
    display_title = StringField(
        _l("Display title"),
        render_kw={
            "placeholder": _l("e.g. Avantisundarīkathā"),
        },
        validators=[DataRequired()],
    )
    status = SelectField(
        _l("Status"),
        choices=[(status.value, status.value) for status in ProjectStatus],
        validators=[DataRequired()],
    )
    description = StringField(
        _l("Description (optional)"),
        widget=TextArea(),
        render_kw={
            "placeholder": _l(
                "What is this book about? Why is this project interesting?"
            ),
        },
    )
    page_numbers = StringField(
        _l("Page numbers (optional)"),
        widget=TextArea(),
        validators=[_is_valid_page_number_spec],
        render_kw={
            "placeholder": "Coming soon.",
        },
    )
    genre = QuerySelectField(
        query_factory=q.genres, allow_blank=True, blank_text=_l("(none)")
    )

    print_title = StringField(
        _l("Print title"),
        render_kw={
            "placeholder": _l(
                "e.g. Śrīdaṇḍimahākaviviracitam avantisundarīkathā nāma gadyakāvyam"
            ),
        },
    )
    author = StringField(
        _l("Author"),
        render_kw={
            "placeholder": _l("The author of the original work, e.g. Kalidasa."),
        },
    )
    editor = StringField(
        _l("Editor"),
        render_kw={
            "placeholder": _l(
                "The person or organization that created this edition, e.g. M.R. Kale."
            ),
        },
    )
    publisher = StringField(
        _l("Publisher"),
        render_kw={
            "placeholder": _l(
                "The original publisher of this book, e.g. Nirnayasagar."
            ),
        },
    )
    worldcat_link = StringField(
        _l("Worldcat link"),
        render_kw={
            "placeholder": _l("A link to this book's entry on worldcat.org."),
        },
    )
    publication_year = StringField(
        _l("Publication year"),
        render_kw={
            "placeholder": _l("The year in which this specific edition was published."),
        },
    )

    notes = StringField(
        _l("Notes (optional)"),
        widget=TextArea(),
        render_kw={
            "placeholder": _l("Internal notes for scholars and other proofreaders."),
        },
    )


class DeleteProjectForm(FlaskForm):
    slug = StringField("Slug", validators=[DataRequired()])


class ReplacePdfForm(FlaskForm):
    pdf_source = RadioField(
        "Source",
        choices=[
            ("url", "Upload from a URL"),
            ("local", "Upload from my computer"),
        ],
        validators=[DataRequired()],
    )
    pdf_url = StringField(
        "PDF URL",
        validators=[_required_if_url("Please provide a valid PDF URL.")],
    )
    local_file = FileField(
        "PDF file",
        validators=[_required_if_local("Please provide a PDF file.")],
    )


@bp.route("/<slug>/")
def summary(slug):
    """Show basic information about the project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    session = q.get_session()
    stmt = (
        sqla.select(db.Revision)
        .options(
            orm.defer(db.Revision.content),
            orm.selectinload(db.Revision.author).load_only(db.User.username),
            orm.selectinload(db.Revision.page).load_only(db.Page.slug),
            orm.selectinload(db.Revision.project).load_only(
                db.Project.slug, db.Project.display_title
            ),
            orm.selectinload(db.Revision.status).load_only(db.PageStatus.name),
        )
        .filter_by(project_id=project_.id)
        .order_by(db.Revision.created_at.desc())
        .limit(10)
    )
    recent_revisions = list(session.scalars(stmt).all())

    page_rules = project_utils.parse_page_number_spec(project_.page_numbers)
    page_titles = project_utils.apply_rules(len(project_.pages), page_rules)
    return render_template(
        "proofing/projects/summary.html",
        project=project_,
        pages=zip(page_titles, project_.pages),
        recent_revisions=recent_revisions,
    )


@bp.route("/<slug>/activity")
def activity(slug):
    """Show recent activity on this project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    session = q.get_session()
    stmt = (
        sqla.select(db.Revision)
        .options(
            orm.defer(db.Revision.content),
            orm.selectinload(db.Revision.author).load_only(db.User.username),
            orm.selectinload(db.Revision.page).load_only(db.Page.slug),
            orm.selectinload(db.Revision.project).load_only(
                db.Project.slug, db.Project.display_title
            ),
            orm.selectinload(db.Revision.status).load_only(db.PageStatus.name),
        )
        .filter_by(project_id=project_.id)
        .order_by(db.Revision.created_at.desc())
        .limit(100)
    )
    recent_revisions = list(session.scalars(stmt).all())
    recent_activity = [("revision", r.created, r) for r in recent_revisions]
    recent_activity.append(("project", project_.created_at, project_))

    return render_template(
        "proofing/projects/activity.html",
        project=project_,
        recent_activity=recent_activity,
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@p2_required
def edit(slug):
    """Edit the project's metadata."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = EditMetadataForm(obj=project_)
    if form.validate_on_submit():
        session = q.get_session()
        new_slug = form.slug.data

        # Check if slug has changed and validate uniqueness
        if new_slug != project_.slug:
            existing_project = q.project(new_slug)
            if existing_project is not None:
                form.slug.errors.append(_l("A project with this slug already exists."))
                return render_template(
                    "proofing/projects/edit.html",
                    project=project_,
                    form=form,
                )

        # Store original status before populate_obj
        original_status = project_.status
        form.populate_obj(project_)

        # Only allow p2 users to change status
        if not current_user.is_p2:
            project_.status = original_status

        descriptions = request.form.getlist("source_description[]")
        urls = request.form.getlist("source_url[]")
        source_ids = request.form.getlist("source_id[]")
        submitted_ids = {int(sid) for sid in source_ids if sid}
        for source in list(project_.sources):
            if source.id not in submitted_ids:
                session.delete(source)
        existing_map = {s.id: s for s in project_.sources}
        for desc, url, sid in zip(descriptions, urls, source_ids):
            desc = desc.strip()
            url = url.strip() or None
            if not desc:
                continue
            if sid and int(sid) in existing_map:
                source = existing_map[int(sid)]
                source.description = desc
                source.url = url
            else:
                session.add(
                    ProjectSource(
                        project_id=project_.id,
                        description=desc,
                        url=url,
                        author_id=current_user.id,
                    )
                )

        session.commit()

        flash(_l("Saved changes."), "success")
        return redirect(url_for("proofing.project.summary", slug=new_slug))

    return render_template(
        "proofing/projects/edit.html",
        project=project_,
        form=form,
    )


@bp.route("/<slug>/download/")
def download(slug):
    """Download the project in various output formats."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    return render_template("proofing/projects/download.html", project=project_)


@bp.route("/<slug>/download/text")
def download_as_text(slug):
    """Download the project as plain text."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    pages = [
        ProofPage.from_content_and_page_id(
            p.revisions[-1].content if p.revisions else "", p.id
        )
        for p in project_.pages
    ]
    raw_text = project_structuring.to_plain_text(pages)

    response = make_response(raw_text, 200)
    response.mimetype = "text/plain"
    return response


@bp.route("/<slug>/download/epub")
def download_as_epub(slug):
    """Download the project as EPUB."""
    import io
    import tempfile
    from pathlib import Path

    from ambuda.utils.text_exports import create_epub

    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_

    # If the project has a published text, use the standard export path.
    text = next(iter(project_.texts), None) if project_.texts else None
    if text is None:
        abort(404)

    with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        create_epub(text, tmp_path)
        epub_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    response = make_response(epub_bytes, 200)
    response.headers["Content-Type"] = "application/epub+zip"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{project_.slug}.epub"'
    )
    return response


@bp.route("/<slug>/download/xml")
def download_as_xml(slug):
    """Download the project as TEI XML.

    This XML will likely have various errors, but it is correct enough that it
    still saves a lot of manual work.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    pages = [
        ProofPage.from_content_and_page_id(
            p.revisions[-1].content if p.revisions else "", p.id
        )
        for p in project_.pages
    ]
    xml_blob = project_structuring.to_tei_xml(pages)

    response = make_response(xml_blob, 200)
    response.mimetype = "text/xml"
    return response


@bp.route("/<slug>/download/project-xml")
@login_required
def download_as_project_xml(slug):
    """Download the project as XML with per-page content and metadata."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    root = ET.Element("project")

    metadata = ET.SubElement(root, "metadata")
    ET.SubElement(metadata, "name").text = project_.display_title or project_.slug
    ET.SubElement(metadata, "pages").text = str(len(project_.pages))
    ET.SubElement(metadata, "downloaded").text = datetime.now(UTC).isoformat()
    ET.SubElement(metadata, "user").text = current_user.username

    for p in project_.pages:
        content = p.revisions[-1].content if p.revisions else ""
        page_el = ET.SubElement(root, "page")
        page_el.set("slug", p.slug)
        page_el.text = content

    xml_bytes = ET.tostring(root, encoding="unicode", xml_declaration=False)
    xml_blob = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes

    response = make_response(xml_blob, 200)
    response.mimetype = "text/xml"
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{project_.slug}.xml"'
    )
    return response


@bp.route("/<slug>/stats")
@moderator_required
def stats(slug):
    """Show basic statistics about this project.

    Currently, these stats don't show any sensitive information. But since that
    might change in the future, limit this page to moderators only.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    stats_ = calculate_stats(project_)
    return render_template(
        "proofing/projects/stats.html", project=project_, stats=stats_
    )


@bp.route("/<slug>/batch-ocr", methods=["GET", "POST"])
@limiter.limit("3/hour", methods=["POST"])
@p2_required
def batch_ocr(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "POST":
        task = ocr_tasks.run_ocr_for_project(
            app_env=current_app.config["AMBUDA_ENVIRONMENT"],
            project=project_,
        )
        if task:
            return render_template(
                "proofing/projects/batch-ocr-post.html",
                project=project_,
                status="PENDING",
                current=0,
                total=0,
                percent=0,
                task_id=task.id,
            )
        else:
            flash(_l("All pages in this project have at least one edit already."))

    return render_template(
        "proofing/projects/batch-ocr.html",
        project=project_,
    )


@bp.route("/batch-ocr-status/<task_id>")
def batch_ocr_status(task_id):
    r = GroupResult.restore(task_id, app=celery_app)
    assert r, task_id

    if r.results:
        current = r.completed_count()
        total = len(r.results)
        percent = current / total

        status = None
        if total:
            if current == total:
                status = "SUCCESS"
            else:
                status = "PROGRESS"
        else:
            status = "FAILURE"

        data = {
            "status": status,
            "current": current,
            "total": total,
            "percent": percent,
        }
    else:
        data = {
            "status": "PENDING",
            "current": 0,
            "total": 0,
            "percent": 0,
        }

    return render_template(
        "include/ocr-progress.html",
        **data,
    )


class BlockDiff(BaseModel):
    type: str
    content: str | None = None
    text: str | None = None
    n: str | None = None
    lang: str | None = None
    mark: str | None = None
    merge_next: bool = False
    index: int | None = None  # Original block index for existing blocks


class PageDiff(BaseModel):
    slug: str
    version: int
    blocks: list[BlockDiff]
    ignore: bool = False


class ProjectDiff(BaseModel):
    project: str
    pages: list[PageDiff]


@bp.route("/<slug>/batch-editing", methods=["GET", "POST"])
@p2_required
def batch_editing(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "POST":
        data = request.form.get("structure_data")
        if not data:
            flash("No data provided", "error")
            return redirect(url_for("proofing.project.batch_editing", slug=slug))

        try:
            project_diff = ProjectDiff.model_validate_json(data)
        except json.JSONDecodeError:
            flash("Invalid structure data format", "error")
            return redirect(url_for("proofing.project.batch_editing", slug=slug))

        # Group all batch changes with a batch ID so we can revert/dedupe later.
        session = q.get_session()
        revision_batch = db.RevisionBatch(user_id=current_user.id)
        session.add(revision_batch)
        session.flush()

        changed_pages = []
        unchanged_pages = []
        errors = []

        page_slugs = []
        for p in project_diff.pages:
            page_slugs.append(p.slug)
        pages = q.pages_with_revisions(project_.id, page_slugs)
        page_map = {p.slug: p for p in pages}

        for page_diff in project_diff.pages:
            if page_diff.ignore:
                continue

            page_slug = page_diff.slug
            if page_slug not in page_map:
                errors.append(f"Page {page_slug} not found")
                continue

            page = page_map[page_slug]
            if not page.revisions:
                errors.append(f"Page {page_slug} has no revisions.")
                continue

            latest_revision = page.revisions[-1]
            old_content = latest_revision.content
            old_structured_page = ProofPage.from_revision(latest_revision)

            new_blocks = []
            had_parse_error = False
            for i, block_data in enumerate(page_diff.blocks):
                content = block_data.content
                if content is None:
                    source_index = block_data.index
                    if source_index is not None:
                        content = old_structured_page.blocks[source_index].content
                    else:
                        content = ""

                try:
                    new_block = ProofBlock(
                        type=block_data.type,
                        content=content,
                        lang=block_data.lang,
                        text=block_data.text,
                        n=block_data.n,
                        mark=block_data.mark,
                        merge_next=block_data.merge_next,
                    )
                except KeyError as e:
                    errors.append(f"Could not parse data for {page_slug}/{i}.")
                    had_parse_error = True
                    break

                new_blocks.append(new_block)

            if had_parse_error:
                errors.append(f"Could not parse edits for {page_slug}.")
                continue

            new_structured_page = ProofPage(blocks=new_blocks, id=page.id)

            new_content = new_structured_page.to_xml_string()
            if old_content == new_content:
                unchanged_pages.append(page_slug)
                continue

            try:
                add_revision(
                    page=page,
                    summary="Batch structuring",
                    content=new_content,
                    version=page_diff.version,
                    author_id=current_user.id,
                    status_id=page.status_id,
                    batch_id=revision_batch.id,
                )
                changed_pages.append(page_slug)
            except Exception as e:
                errors.append(f"Failed to save page {page_slug}: {str(e)}")
                LOG.error(f"Failed to save batch structuring for {page_slug}: {e}")

        _plural = lambda n: "s" if n > 1 else ""

        message_parts = []
        if changed_pages:
            message_parts.append(
                f"Saved {len(changed_pages)} changed page{_plural(len(changed_pages))}"
            )
        if unchanged_pages:
            message_parts.append(f"{len(unchanged_pages)} unchanged")
        if not changed_pages and not unchanged_pages:
            message_parts.append("No pages to save")

        message = ", ".join(message_parts) + "."
        if errors:
            message += f" ({len(errors)} error{_plural(len(errors))})"
            flash(message, "warning")
        elif len(changed_pages) > 0:
            flash(message, "success")
        else:
            flash(message, "info")

        return redirect(url_for("proofing.project.summary", slug=slug))

    pages_with_content = []
    for page in project_.pages:
        if page.revisions:
            latest_revision = page.revisions[-1]
            structured_data = ProofPage.from_revision(latest_revision)

            pages_with_content.append(
                {
                    "slug": page.slug,
                    "version": page.version,
                    "blocks": structured_data.blocks,
                }
            )

    return render_template(
        "proofing/projects/batch-editing.html",
        project=project_,
        pages_with_content=pages_with_content,
        block_types=BLOCK_TYPES,
        languages=LANGUAGES,
    )


@bp.route("/<slug>/parse-content", methods=["POST"])
@login_required
def parse_content(slug):
    """Parse content and return structured blocks.

    This is a convenience API for the batch editing workflow.
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    data = request.get_json()
    if not data or "content" not in data:
        return jsonify({"error": "No content provided"}), 400

    content = data["content"]
    if not content or not content.strip():
        return jsonify({"error": "Content is empty"}), 400

    try:
        # page_id is not used, so use a dummy value
        parsed_page = ProofPage.from_content_and_page_id(content, page_id=0)
        blocks = []
        for block in parsed_page.blocks:
            blocks.append(
                {
                    "type": block.type,
                    "content": block.content,
                    "lang": block.lang,
                    "text": block.text,
                    "n": block.n,
                    "mark": block.mark,
                    "merge_next": block.merge_next,
                }
            )

        return jsonify({"blocks": blocks})
    except Exception as e:
        LOG.error(f"Failed to parse content: {e}")
        return jsonify({"error": f"Failed to parse content: {str(e)}"}), 500


@bp.route("/<slug>/batch-llm-structuring", methods=["GET", "POST"])
@limiter.limit("3/hour", methods=["POST"])
def batch_llm_structuring(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "POST":
        task = llm_structuring_tasks.run_structuring_for_project(
            app_env=current_app.config["AMBUDA_ENVIRONMENT"],
            project=project_,
        )
        if task:
            return render_template(
                "proofing/projects/batch-llm-structuring-post.html",
                project=project_,
                status="PENDING",
                current=0,
                total=0,
                percent=0,
                task_id=task.id,
            )
        else:
            flash(_l("No edited pages found in this project."))

    return render_template(
        "proofing/projects/batch-llm-structuring.html",
        project=project_,
    )


@bp.route("/batch-llm-structuring-status/<task_id>")
def batch_llm_structuring_status(task_id):
    r = GroupResult.restore(task_id, app=celery_app)
    assert r, task_id

    if r.results:
        current = r.completed_count()
        total = len(r.results)
        percent = current / total

        status = None
        if total:
            if current == total:
                status = "SUCCESS"
            else:
                status = "PROGRESS"
        else:
            status = "FAILURE"

        data = {
            "status": status,
            "current": current,
            "total": total,
            "percent": percent,
        }
    else:
        data = {
            "status": "PENDING",
            "current": 0,
            "total": 0,
            "percent": 0,
        }

    return render_template(
        "include/llm-structuring-progress.html",
        **data,
    )


@bp.route("/<slug>/batch-llm", methods=["GET", "POST"])
@limiter.limit("3/hour", methods=["POST"])
@p2_required
def batch_llm(slug):
    """Run a batch LLM prompt over a range of pages, storing results as suggestions."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "GET":
        return render_template(
            "proofing/projects/batch-llm.html",
            project=project_,
            total_pages=len(project_.pages),
            preset_prompts=PRESET_PROMPTS,
        )

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400

    prompt_key = data.get("prompt")
    custom_prompt = data.get("custom_prompt")
    page_start = data.get("page_start")
    page_end = data.get("page_end")

    if not page_start or not page_end:
        return jsonify({"error": "page_start and page_end are required"}), 400

    # Resolve prompt template
    if prompt_key and prompt_key in PRESET_PROMPTS:
        prompt_template = PRESET_PROMPTS[prompt_key]["template"]
    elif custom_prompt:
        if "{content}" not in custom_prompt:
            return jsonify(
                {"error": "Custom prompt must contain {content} placeholder"}
            ), 400
        prompt_template = custom_prompt
    else:
        return jsonify({"error": "A valid preset or custom prompt is required"}), 400

    # Find the order range from start/end page slugs
    start_slug = str(page_start)
    end_slug = str(page_end)
    start_order = None
    end_order = None
    for p in project_.pages:
        if p.slug == start_slug:
            start_order = p.order
        if p.slug == end_slug:
            end_order = p.order

    if start_order is None or end_order is None:
        return jsonify({"error": "Invalid page range"}), 400

    # Filter pages within the order range that have content
    page_slugs = [
        p.slug
        for p in project_.pages
        if start_order <= p.order <= end_order and p.version > 0
    ]

    if not page_slugs:
        return jsonify({"error": "No edited pages found in the given range"}), 400

    batch_id = str(uuid.uuid4())
    task = batch_llm_tasks.run_batch_llm_for_project(
        app_env=current_app.config["AMBUDA_ENVIRONMENT"],
        project=project_,
        prompt_template=prompt_template,
        page_slugs=page_slugs,
        batch_id=batch_id,
    )

    if task:
        redirect_url = url_for(
            "proofing.project.batch_llm_progress", slug=slug, task_id=task.id
        )
        return jsonify({"redirect": redirect_url})
    else:
        return jsonify({"error": "Failed to start batch LLM task"}), 500


@bp.route("/<slug>/batch-llm-progress/<task_id>")
@p2_required
def batch_llm_progress(slug, task_id):
    """Show the progress page for a batch LLM run."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    return render_template(
        "proofing/projects/batch-llm-progress.html",
        project=project_,
        task_id=task_id,
        status="PENDING",
    )


@bp.route("/batch-llm-status/<task_id>")
def batch_llm_status(task_id):
    """Poll the status of a batch LLM task."""
    from celery.result import AsyncResult

    r = AsyncResult(task_id, app=celery_app)
    state = r.state  # PENDING, STARTED, SUCCESS, FAILURE, etc.

    if state == "SUCCESS":
        result = r.result or {}
        data = {
            "status": "SUCCESS",
            "created": result.get("created", 0),
            "skipped": result.get("skipped", 0),
            "total": result.get("total", 0),
        }
    elif state == "FAILURE":
        data = {"status": "FAILURE", "error": str(r.result)}
    elif state == "PENDING":
        data = {"status": "PENDING"}
    else:
        # STARTED or any other active state
        data = {"status": "PROGRESS"}

    return render_template(
        "include/batch-llm-progress.html",
        **data,
    )


@bp.route("/<slug>/reorder-pages", methods=["GET", "POST"])
@p2_required
def reorder_pages(slug):
    """Reorder the pages in a project."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "POST":
        data = request.get_json()
        if not data or "page_ids" not in data:
            return jsonify({"error": "No page_ids provided"}), 400

        page_ids = data["page_ids"]
        project_page_ids = {p.id for p in project_.pages}
        if set(page_ids) != project_page_ids:
            return jsonify({"error": "Invalid page IDs"}), 400

        image_uuids = data.get("image_uuids")
        if image_uuids is not None:
            project_uuids = {p.uuid for p in project_.pages}
            if set(image_uuids) != project_uuids:
                return jsonify({"error": "Invalid image UUIDs"}), 400

        session = q.get_session()
        order_mapping = {page_id: i for i, page_id in enumerate(page_ids)}
        session.execute(
            sqla.update(db.Page)
            .where(db.Page.id.in_(page_ids))
            .values(order=sqla.case(order_mapping, value=db.Page.id))
        )
        if image_uuids is not None:
            tmp_mapping = {pid: f"tmp-{pid}" for pid in page_ids}
            uuid_mapping = dict(zip(page_ids, image_uuids))
            for mapping in [tmp_mapping, uuid_mapping]:
                session.execute(
                    sqla.update(db.Page)
                    .where(db.Page.id.in_(page_ids))
                    .values(uuid=sqla.case(mapping, value=db.Page.id))
                )
        session.commit()
        return jsonify({"ok": True})

    pages_data = []
    for page in project_.pages:
        latest = page.revisions[-1] if page.revisions else None
        preview = latest.content[:200] if latest else ""
        pages_data.append(
            {
                "id": page.id,
                "slug": page.slug,
                "uuid": page.uuid,
                "order": page.order,
                "preview": preview,
            }
        )

    return render_template(
        "proofing/projects/reorder.html",
        project=project_,
        pages_data=pages_data,
    )


@bp.route("/<slug>/admin", methods=["GET", "POST"])
@moderator_required
def admin(slug):
    """View admin controls for the project.

    We restrict these operations to admins because they are destructive in the
    wrong hands. Current list of admin operations:

    - delete project
    """
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = DeleteProjectForm()
    if form.validate_on_submit():
        if form.slug.data == slug:
            project_tasks.delete_project.delay(
                project_slug=slug,
                app_environment=current_app.config["AMBUDA_ENVIRONMENT"],
            )

            flash(f"Deleted project {slug}")
            return redirect(url_for("proofing.index"))
        else:
            form.slug.errors.append("Deletion failed (incorrect field value).")

    return render_template(
        "proofing/projects/admin.html",
        project=project_,
        form=form,
    )


@bp.route("/<slug>/replace-pdf", methods=["GET", "POST"])
@p2_required
def replace_pdf(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = ReplacePdfForm()
    if not form.validate_on_submit():
        return render_template(
            "proofing/projects/replace-pdf.html",
            project=project_,
            form=form,
        )

    pdf_source = form.pdf_source.data

    app_env = current_app.config["AMBUDA_ENVIRONMENT"]

    if pdf_source == "url":
        pdf_url = form.pdf_url.data
        pdf_task = project_tasks.replace_project_pdf_from_url.si(
            project_slug=slug,
            pdf_url=pdf_url,
            app_environment=app_env,
        )
    else:
        filename = form.local_file.raw_data[0].filename
        if not _is_allowed_document_file(filename):
            flash("Please upload a PDF.")
            return render_template(
                "proofing/projects/replace-pdf.html",
                project=project_,
                form=form,
            )

        file_data = form.local_file.data
        file_data.seek(0, 2)
        size = file_data.tell()
        file_data.seek(0)
        if size > 128 * 1024 * 1024:
            flash("PDF must be under 128 MB.")
            return render_template(
                "proofing/projects/replace-pdf.html",
                project=project_,
                form=form,
            )

        upload_dir = Path(current_app.config["UPLOAD_FOLDER"]) / "pdf-upload"
        upload_dir.mkdir(parents=True, exist_ok=True)

        temp_id = str(uuid.uuid4())
        pdf_path = upload_dir / f"{temp_id}.pdf"
        form.local_file.data.save(pdf_path)

        pdf_task = project_tasks.replace_project_pdf.si(
            project_slug=slug,
            pdf_path=str(pdf_path),
            app_environment=app_env,
        )

    task = pdf_task.apply_async()

    return render_template(
        "proofing/projects/replace-pdf-post.html",
        project=project_,
        status=task.status,
        current=0,
        total=0,
        percent=0,
        task_id=task.id,
    )


@bp.route("/<slug>/replace-ocr-bounding-boxes", methods=["GET", "POST"])
@limiter.limit("3/hour", methods=["POST"])
@p2_required
def replace_ocr_bounding_boxes(slug):
    """Re-run OCR to update bounding box data for all pages without creating new revisions."""
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    assert project_
    if request.method == "POST":
        task = ocr_tasks.replace_ocr_bounding_boxes(
            app_env=current_app.config["AMBUDA_ENVIRONMENT"],
            project=project_,
        )
        if task:
            return render_template(
                "proofing/projects/batch-ocr-post.html",
                project=project_,
                status="PENDING",
                current=0,
                total=0,
                percent=0,
                task_id=task.id,
            )
        else:
            flash(_l("This project has no pages."))

    return render_template(
        "proofing/projects/replace-ocr-bounding-boxes.html",
        project=project_,
    )
