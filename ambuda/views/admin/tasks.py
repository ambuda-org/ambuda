import json
import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from flask import (
    current_app,
    request,
    redirect,
    url_for,
    flash,
    render_template,
    jsonify,
    make_response,
)
from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, MultipleFileField
from sqlalchemy import inspect, select
from sqlalchemy.orm import selectinload
from sqlalchemy.types import DateTime
from wtforms import SelectField
from wtforms.validators import DataRequired

import ambuda.database as db
import ambuda.queries as q
import ambuda.data_utils as data_utils
from ambuda.models.proofing import _create_uuid
from ambuda.utils.text_exports import ExportType
from ambuda.tasks.text_exports import (
    delete_text_export,
    create_all_exports_for_text,
    populate_file_cache,
)
from ambuda.tasks.projects import regenerate_project_pages
from ambuda.utils.tei_parser import parse_document

_UPLOAD_MAX_SIZE = 128 * 1024 * 1024


def _check_file_size(file, max_size=_UPLOAD_MAX_SIZE):
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > max_size:
        raise ValueError(f"File exceeds {max_size // (1024 * 1024)} MB limit")
    return size


def get_model_configs_context():
    """Get model configs for template context."""
    from .main import MODEL_CONFIG, get_models_by_category

    return {
        "model_configs": {c.model.__name__: c for c in MODEL_CONFIG},
        "models_by_category": get_models_by_category(),
    }


def import_text(model_name, selected_ids: list | None = None):
    """Import texts from XML files."""

    class UploadTextForm(FlaskForm):
        xml_files = MultipleFileField("XML Files", validators=[FileRequired()])

    form = UploadTextForm()

    if form.validate_on_submit():
        xml_files = form.xml_files.data
        session = q.get_session()

        success_count = 0
        error_count = 0
        errors = []

        for index, xml_file in enumerate(xml_files):
            filename = xml_file.filename
            if not filename.endswith(".xml"):
                errors.append(f"{filename}: Must be an XML file")
                error_count += 1
                continue

            # Get slug and title from form data
            slug = request.form.get(f"slug_{index}", "").strip()
            title = request.form.get(f"title_{index}", "").strip()

            if not slug:
                errors.append(f"{filename}: Slug is required")
                error_count += 1
                continue
            if not title:
                errors.append(f"{filename}: Title is required")
                error_count += 1
                continue

            stmt = select(db.Text).filter_by(slug=slug)
            if session.scalars(stmt).first():
                errors.append(f"{filename}: A text with slug '{slug}' already exists")
                error_count += 1
                continue

            tmp_path = None
            try:
                _check_file_size(xml_file)

                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".xml", delete=False
                ) as tmp_file:
                    xml_file.save(tmp_file)
                    tmp_path = Path(tmp_file.name)

                document = parse_document(tmp_path)
                data_utils.create_text_from_document(session, slug, title, document)
                success_count += 1

            except Exception as e:
                session.rollback()
                errors.append(f"{filename}: {str(e)}")
                error_count += 1
            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()

        if success_count > 0:
            flash(f"Successfully uploaded {success_count} text(s)", "success")
        if error_count > 0:
            flash(
                f"{error_count} error(s): {'; '.join(errors[:5])}{'...' if len(errors) > 5 else ''}",
                "error",
            )

        if success_count > 0 or error_count > 0:
            return redirect(url_for("admin.list_model", model_name=model_name))

    return render_template(
        "admin/task-import-text.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


def import_parse_data(model_name, selected_ids: list | None = None):
    """Import parse data for texts from TXT files."""

    class UploadParseDataForm(FlaskForm):
        parse_files = MultipleFileField("Parse Data Files", validators=[FileRequired()])

    form = UploadParseDataForm()

    if form.validate_on_submit():
        parse_files = form.parse_files.data
        session = q.get_session()

        success_count = 0
        error_count = 0
        errors = []

        for parse_file in parse_files:
            # Derive text slug from filename (e.g., "bhagavad-gita.txt" -> "bhagavad-gita")
            filename = parse_file.filename
            if not filename.endswith(".txt"):
                errors.append(f"{filename}: Must be a .txt file")
                error_count += 1
                continue

            text_slug = filename[:-4]  # Remove .txt extension

            stmt = select(db.Text).filter_by(slug=text_slug)
            text = session.scalars(stmt).first()
            if not text:
                errors.append(f"{filename}: Text with slug '{text_slug}' not found")
                error_count += 1
                continue

            tmp_path = None
            try:
                _check_file_size(parse_file)

                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".txt", delete=False
                ) as tmp_file:
                    parse_file.save(tmp_file)
                    tmp_path = Path(tmp_file.name)

                data_utils.add_parse_data(session, text_slug, tmp_path)
                success_count += 1

            except Exception as e:
                session.rollback()
                errors.append(f"{filename}: {str(e)}")
                error_count += 1
            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()

        if success_count > 0:
            flash(
                f"Successfully uploaded parse data for {success_count} text(s)",
                "success",
            )
        if error_count > 0:
            flash(
                f"{error_count} error(s): {'; '.join(errors[:5])}{'...' if len(errors) > 5 else ''}",
                "error",
            )

        if success_count > 0 or error_count > 0:
            return redirect(url_for("admin.list_model", model_name=model_name))

    return render_template(
        "admin/task-import-parse-data.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


def add_genre_to_texts(model_name, selected_ids: list | None = None):
    """Batch action to add a genre to multiple texts."""

    class AddGenreForm(FlaskForm):
        genre_id = SelectField("Genre", coerce=int, validators=[DataRequired()])

    session = q.get_session()
    genres = session.query(db.Genre).order_by(db.Genre.name).all()

    form = AddGenreForm()
    form.genre_id.choices = [(g.id, g.name) for g in genres]

    if not selected_ids:
        flash("No texts selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    if form.validate_on_submit():
        genre_id = form.genre_id.data

        try:
            updated_count = 0
            for text_id in selected_ids:
                text = session.get(db.Text, int(text_id))
                if text:
                    text.genre_id = genre_id
                    updated_count += 1

            session.commit()
            genre_name = session.get(db.Genre, genre_id).name
            flash(
                f"Successfully added genre '{genre_name}' to {updated_count} text(s)",
                "success",
            )
            return redirect(url_for("admin.list_model", model_name=model_name))

        except Exception as e:
            session.rollback()
            flash(f"Error adding genre: {str(e)}", "error")

    texts = []
    for text_id in selected_ids:
        text = session.get(db.Text, int(text_id))
        if text:
            texts.append(text)

    return render_template(
        "admin/task-add-genre.html",
        model_name=model_name,
        form=form,
        texts=texts,
        selected_ids=selected_ids,
        **get_model_configs_context(),
    )


def import_metadata(model_name, selected_ids: list | None = None):
    """Import text metadata from a JSON file."""

    class UploadMetadataForm(FlaskForm):
        json_file = FileField("JSON File", validators=[FileRequired()])

    form = UploadMetadataForm()

    if form.validate_on_submit():
        json_file = form.json_file.data

        session = q.get_session()
        try:
            _check_file_size(json_file)
            metadata_list = json.load(json_file.stream)

            updated_count, not_found_slugs = data_utils.import_text_metadata(
                session, metadata_list
            )

            if not_found_slugs:
                flash(
                    (
                        f"Updated {updated_count} text(s). "
                        f"Warning: {len(not_found_slugs)} slug(s) not found: "
                        f"{', '.join(not_found_slugs[:5])}{'...' if len(not_found_slugs) > 5 else ''}"
                    ),
                    "warning",
                )
            else:
                flash(f"Successfully updated {updated_count} text(s)", "success")

            return redirect(url_for("admin.list_model", model_name=model_name))

        except Exception as e:
            session.rollback()
            flash(f"Error importing metadata: {str(e)}", "error")

    return render_template(
        "admin/task-import-metadata.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


def export_metadata(model_name, selected_ids: list | None = None):
    """Export Text metadata as JSON."""
    from ambuda.utils.text_utils import text_metadata

    session = q.get_session()

    if not selected_ids:
        selected_ids = []

    text_ids = [int(id_str) for id_str in selected_ids]
    texts = session.query(db.Text).filter(db.Text.id.in_(text_ids)).all()
    export_data = [text_metadata(t) for t in texts]

    response = make_response(jsonify(export_data))
    response.headers["Content-Disposition"] = "attachment; filename=texts_metadata.json"
    response.headers["Content-Type"] = "application/json"

    return response


def import_dictionaries(model_name, selected_ids: list | None = None):
    """Import dictionaries from XML files."""

    class UploadDictionaryForm(FlaskForm):
        xml_files = MultipleFileField("XML Files", validators=[FileRequired()])

    form = UploadDictionaryForm()

    if form.validate_on_submit():
        xml_files = form.xml_files.data
        session = q.get_session()

        success_count = 0
        error_count = 0
        errors = []
        total_entries = 0

        for index, xml_file in enumerate(xml_files):
            filename = xml_file.filename
            if not filename.endswith(".xml"):
                errors.append(f"{filename}: Must be an XML file")
                error_count += 1
                continue

            slug = request.form.get(f"slug_{index}", "").strip()
            title = request.form.get(f"title_{index}", "").strip()

            if not slug:
                errors.append(f"{filename}: Slug is required")
                error_count += 1
                continue
            if not title:
                errors.append(f"{filename}: Title is required")
                error_count += 1
                continue

            session = q.get_session()
            stmt = select(db.Dictionary).filter_by(slug=slug)
            dictionary = session.scalars(stmt).first()
            if dictionary:
                errors.append(
                    f"{filename}: A dictionary with slug '{slug}' already exists"
                )
                error_count += 1
                continue

            tmp_path = None
            try:
                _check_file_size(xml_file)

                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".xml", delete=False
                ) as tmp_file:
                    xml_file.save(tmp_file)
                    tmp_path = Path(tmp_file.name)

                entry_count = data_utils.import_dictionary_from_xml(
                    slug=slug, title=title, path=tmp_path
                )
                total_entries += entry_count
                success_count += 1

            except Exception as e:
                session.rollback()
                errors.append(f"{filename}: {str(e)}")
                error_count += 1
            finally:
                if tmp_path and tmp_path.exists():
                    tmp_path.unlink()

        # Display summary
        if success_count > 0:
            flash(
                (
                    f"Successfully imported {success_count} dictionar{'ies' if success_count > 1 else 'y'} "
                    f"({total_entries} entries)"
                ),
                "success",
            )
        if error_count > 0:
            flash(
                f"{error_count} error(s): {'; '.join(errors[:5])}{'...' if len(errors) > 5 else ''}",
                "error",
            )

        if success_count > 0 or error_count > 0:
            return redirect(url_for("admin.list_model", model_name=model_name))

    return render_template(
        "admin/task-import-dictionary.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


def serialize(obj, exclude=None) -> dict:
    if exclude is None:
        exclude = set()

    mapper = inspect(obj.__class__)
    result = {}
    for column in mapper.columns:
        if column.name in exclude:
            continue
        value = getattr(obj, column.name)
        if isinstance(value, datetime):
            result[column.name] = value.isoformat()
        else:
            result[column.name] = value
    return result


def deserialize(data: dict, model_class):
    obj = model_class()
    mapper = inspect(model_class)
    for column in mapper.columns:
        # To avoid collisions with prod data.
        if column.primary_key:
            continue

        if column.name in data:
            value = data[column.name]
            if isinstance(column.type, DateTime) and value is not None:
                if isinstance(value, str):
                    value = datetime.fromisoformat(value)
            setattr(obj, column.name, value)
    return obj


def export_projects(model_name, selected_ids: list | None = None):
    session = q.get_session()
    query = session.query(db.Project).options(
        selectinload(db.Project.pages).selectinload(db.Page.revisions),
        selectinload(db.Project.publish_configs),
    )

    if not selected_ids:
        selected_ids = []

    project_ids = [int(id_str) for id_str in selected_ids]
    query = query.filter(db.Project.id.in_(project_ids))

    projects = query.all()

    export_data = {"projects": []}
    for project in projects:
        project_dict = serialize(
            project, exclude={"id", "creator_id", "board_id", "genre_id"}
        )
        project_dict["pages"] = []

        for page in project.pages:
            page_dict = serialize(page, exclude={"id", "status_id"})
            page_dict["revisions"] = []

            for revision in page.revisions:
                revision_dict = serialize(
                    revision, exclude={"id", "author_id", "status_id"}
                )
                page_dict["revisions"].append(revision_dict)

            project_dict["pages"].append(page_dict)

        project_dict["publish_configs"] = [
            serialize(pc, exclude={"id", "project_id", "text_id"})
            for pc in project.publish_configs
        ]

        export_data["projects"].append(project_dict)

    response = make_response(jsonify(export_data))
    response.headers["Content-Disposition"] = (
        "attachment; filename=projects_export.json"
    )
    response.headers["Content-Type"] = "application/json"
    return response


def import_projects(model_name, selected_ids: list | None = None):
    class UploadProjectsForm(FlaskForm):
        json_file = FileField("JSON File", validators=[FileRequired()])

    form = UploadProjectsForm()

    if not form.validate_on_submit():
        return render_template(
            "admin/task-import-projects.html",
            model_name=model_name,
            form=form,
            **get_model_configs_context(),
        )

    json_file = form.json_file.data
    session = q.get_session()

    try:
        bot_user = session.query(db.User).filter_by(username="ambuda-bot").first()
        if not bot_user:
            flash("Error: ambuda-bot user not found in database", "error")
            return render_template(
                "admin/task-import-projects.html",
                model_name=model_name,
                form=form,
                **get_model_configs_context(),
            )

        # TODO: assign a real status.
        status = session.query(db.PageStatus).first()
        if not status:
            flash("Error: No page status found in database", "error")
            return render_template(
                "admin/task-import-projects.html",
                model_name=model_name,
                form=form,
                **get_model_configs_context(),
            )

        _check_file_size(json_file)
        data = json.load(json_file.stream)
        projects_data = data.get("projects", [])

        success_count = 0
        for project_data in projects_data:
            pages_data = project_data.pop("pages", [])
            publish_configs_data = project_data.pop("publish_configs", [])

            board = db.Board(title=f"Board for {project_data.get('slug', 'project')}")
            session.add(board)
            session.flush()

            project_data["board_id"] = board.id
            project_data["creator_id"] = bot_user.id
            project_data["genre_id"] = None

            project = deserialize(project_data, db.Project)
            session.add(project)
            session.flush()

            for page_data in pages_data:
                revisions_data = page_data.pop("revisions", [])
                page_data["project_id"] = project.id
                page_data["status_id"] = status.id

                page = deserialize(page_data, db.Page)
                # Set a new uuid to avoid conflicts
                page.uuid = _create_uuid()
                session.add(page)
                session.flush()

                for revision_data in revisions_data:
                    revision_data["project_id"] = project.id
                    revision_data["page_id"] = page.id
                    revision_data["author_id"] = bot_user.id
                    revision_data["status_id"] = status.id

                    revision = deserialize(revision_data, db.Revision)
                    session.add(revision)

            for pc_data in publish_configs_data:
                pc_data["project_id"] = project.id
                pc = deserialize(pc_data, db.PublishConfig)
                session.add(pc)

            success_count += 1

        session.commit()
        flash(f"Successfully imported {success_count} project(s)", "success")
        return redirect(url_for("admin.list_model", model_name=model_name))

    except Exception as e:
        session.rollback()
        flash(f"Error importing projects: {str(e)}", "error")

    return render_template(
        "admin/task-import-projects.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


class CollectionExport(BaseModel):
    slug: str
    title: str
    order: int = 0
    description: str | None = None
    parent_slug: str | None = None
    text_slugs: list[str] = Field(default_factory=list)


class CollectionExportData(BaseModel):
    collections: list[CollectionExport] = Field(default_factory=list)


def export_collections(model_name, selected_ids: list | None = None):
    """Export TextCollections as JSON, with hierarchy and text associations."""
    session = q.get_session()
    query = session.query(db.TextCollection).options(
        selectinload(db.TextCollection.texts),
    )

    if not selected_ids:
        selected_ids = []

    collection_ids = [int(id_str) for id_str in selected_ids]
    query = query.filter(db.TextCollection.id.in_(collection_ids))
    collections = query.all()

    # Build a lookup from id -> slug for parent references
    all_collections = session.query(db.TextCollection).all()
    id_to_slug = {c.id: c.slug for c in all_collections}

    items = []
    for collection in collections:
        items.append(
            CollectionExport(
                slug=collection.slug,
                title=collection.title,
                order=collection.order,
                description=collection.description,
                parent_slug=id_to_slug.get(collection.parent_id)
                if collection.parent_id
                else None,
                text_slugs=[t.slug for t in collection.texts],
            )
        )

    export_data = CollectionExportData(collections=items)

    response = make_response(export_data.model_dump_json(indent=2))
    response.headers["Content-Disposition"] = (
        "attachment; filename=collections_export.json"
    )
    response.headers["Content-Type"] = "application/json"
    return response


def import_collections(model_name, selected_ids: list | None = None):
    """Import TextCollections from a JSON file."""

    class UploadCollectionsForm(FlaskForm):
        json_file = FileField("JSON File", validators=[FileRequired()])

    form = UploadCollectionsForm()

    if not form.validate_on_submit():
        return render_template(
            "admin/task-import-collections.html",
            model_name=model_name,
            form=form,
            **get_model_configs_context(),
        )

    json_file = form.json_file.data
    session = q.get_session()

    try:
        _check_file_size(json_file)
        raw = json_file.stream.read()
        export_data = CollectionExportData.model_validate_json(raw)

        # First pass: create or update collections (without parent links)
        slug_to_info: dict[str, tuple[db.TextCollection, CollectionExport]] = {}
        success_count = 0
        for item in export_data.collections:
            existing = session.query(db.TextCollection).filter_by(slug=item.slug).first()
            if existing:
                existing.title = item.title
                existing.order = item.order
                existing.description = item.description
                collection = existing
            else:
                collection = db.TextCollection(
                    slug=item.slug,
                    title=item.title,
                    order=item.order,
                    description=item.description,
                )
                session.add(collection)

            slug_to_info[item.slug] = (collection, item)
            success_count += 1

        session.flush()

        # Second pass: set parent references and text associations
        for slug, (collection, item) in slug_to_info.items():
            if item.parent_slug:
                parent = (
                    session.query(db.TextCollection)
                    .filter_by(slug=item.parent_slug)
                    .first()
                )
                if parent:
                    collection.parent_id = parent.id

            if item.text_slugs:
                texts = (
                    session.query(db.Text)
                    .filter(db.Text.slug.in_(item.text_slugs))
                    .all()
                )
                collection.texts = texts

        session.commit()
        flash(f"Successfully imported {success_count} collection(s)", "success")
        return redirect(url_for("admin.list_model", model_name=model_name))

    except Exception as e:
        session.rollback()
        flash(f"Error importing collections: {str(e)}", "error")

    return render_template(
        "admin/task-import-collections.html",
        model_name=model_name,
        form=form,
        **get_model_configs_context(),
    )


def run_quality_reports(model_name, selected_ids: list | None = None):
    """Batch action to run quality reports for selected texts."""
    if not selected_ids:
        flash("No texts selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    from ambuda.tasks.text_validation import run_report

    session = q.get_session()
    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]

    task_count = 0
    for text_id in selected_ids:
        text = session.get(db.Text, int(text_id))
        if not text:
            continue

        run_report.apply_async(
            args=(text.id, app_environment),
            headers={"initiated_by": current_user.username},
        )
        task_count += 1

    flash(f"Started quality report for {task_count} text(s).", "success")
    return redirect(url_for("admin.list_model", model_name=model_name))


def create_exports(model_name, selected_ids: list | None = None):
    """Batch action to create all exports for selected texts."""
    if not selected_ids:
        flash("No texts selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    session = q.get_session()
    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]

    chain_count = 0
    for text_id in selected_ids:
        text = session.get(db.Text, int(text_id))
        if not text:
            continue

        export_chain = create_all_exports_for_text(
            text_id=text.id,
            app_environment=app_environment,
        )
        export_chain.apply_async(headers={"initiated_by": current_user.username})
        chain_count += 1

    flash(f"Started export for {chain_count} text(s).", "success")
    return redirect(url_for("admin.list_model", model_name=model_name))


def delete_exports(model_name, selected_ids: list | None = None):
    if not selected_ids:
        flash("No exports selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    session = q.get_session()
    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]
    task_count = 0
    for export_id in selected_ids:
        text_export = session.get(db.TextExport, int(export_id))
        if not text_export:
            continue

        delete_text_export.apply_async(
            kwargs=dict(
                export_id=text_export.id,
                app_environment=app_environment,
            ),
            headers={"initiated_by": current_user.username},
        )
        task_count += 1

    flash(
        f"Started {task_count} deletion task(s) for {len(selected_ids)} export(s)",
        "success",
    )
    return redirect(url_for("admin.list_model", model_name=model_name))


def save_xml_to_disk_cache(model_name, selected_ids: list | None = None):
    """Download all XML exports from S3 and save them to the local file cache."""
    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]
    populate_file_cache.apply_async(
        kwargs=dict(app_environment=app_environment),
        headers={"initiated_by": current_user.username},
    )
    flash("Started saving XML files to disk cache.", "success")
    return redirect(url_for("admin.list_model", model_name=model_name))


def export_text_archive(model_name, selected_ids: list | None = None):
    """Batch action to export selected texts as a ZIP archive to S3."""
    if not selected_ids:
        flash("No texts selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    from ambuda.tasks.text_archive import create_text_archive

    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]
    text_ids = [int(id_str) for id_str in selected_ids]

    create_text_archive.apply_async(
        args=(text_ids, app_environment),
        headers={"initiated_by": current_user.username},
    )

    flash(f"Started text archive export for {len(text_ids)} text(s).", "success")
    return redirect(url_for("admin.list_model", model_name=model_name))


def regenerate_pages(model_name, selected_ids: list | None = None):
    """Batch action to regenerate page images for selected projects."""
    if not selected_ids:
        flash("No projects selected", "error")
        return redirect(url_for("admin.list_model", model_name=model_name))

    session = q.get_session()
    app_environment = current_app.config["AMBUDA_ENVIRONMENT"]

    task_count = 0
    for project_id in selected_ids:
        project = session.get(db.Project, int(project_id))
        if not project:
            continue

        regenerate_project_pages.apply_async(
            kwargs=dict(
                project_slug=project.slug,
                app_environment=app_environment,
            ),
            headers={"initiated_by": current_user.username},
        )
        task_count += 1

    flash(
        f"Started page regeneration for {task_count} project(s).",
        "success",
    )
    return redirect(url_for("admin.list_model", model_name=model_name))
