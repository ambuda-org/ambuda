"""Ambuda admin interface."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from flask import (
    Blueprint,
    render_template,
    abort,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_login import current_user
from flask_wtf import FlaskForm
from sqlalchemy import func, inspect, Text, JSON
from sqlalchemy.exc import SQLAlchemyError
from wtforms import (
    Form,
    StringField,
    IntegerField,
    TextAreaField,
    BooleanField,
    DateTimeField,
    DateTimeLocalField,
    SelectField,
    SelectMultipleField,
)
from wtforms.validators import Optional

import ambuda.database as db
import ambuda.queries as q
from ambuda.models.proofing import ProjectStatus
from ambuda.models.texts import TextStatus
from ambuda.views.admin import tasks


bp = Blueprint("admin", __name__)
FK_DROPDOWN_LIMIT = 500


class Category(str, Enum):
    """Model categories (for sidebar grouping)"""

    AUTH = "Auth"
    TEXTS = "Texts"
    DICTIONARIES = "Dictionaries"
    PROOFING = "Proofing"
    SITE = "Site"
    DISCUSSION = "Discussion"
    BLOG = "Blog"
    PARSE_DATA = "Tagging"


@dataclass
class Task:
    """An adhoc task associated with some model."""

    #: The display name of the task.
    name: str
    #: The URL name of the task.
    slug: str
    #: The function to call.
    handler: Callable


@dataclass
class ModelConfig:
    """Defines how to display a model in the admin UI."""

    #: The model name.
    model: Any
    #: Columns that appear in list view.
    list_columns: list[str]
    #: Model category (for sidebar grouping)
    category: Category
    #: Tasks associated with the model (upload, etc.)
    tasks: list[Task] = field(default_factory=list)
    #: If set, the model can't be mutated.
    read_only: bool = False
    #: Permission required: 'admin' or 'moderator'. Defaults to 'admin'.
    permission: str = "admin"
    #: Field to display for foreign keys (e.g., 'slug', 'username'). If None, shows ID.
    display_field: str | None = None
    #: Enum classes for string fields (e.g., {'status': TextStatus})
    enum_fields: dict[str, type] = field(default_factory=dict)
    search_key: str | None = None


MODEL_CONFIG = [
    ModelConfig(
        model=db.Author,
        list_columns=["id", "name"],
        category=Category.TEXTS,
        display_field="name",
    ),
    ModelConfig(
        model=db.BlockParse,
        list_columns=["id", "text_id", "block_id"],
        category=Category.PARSE_DATA,
        read_only=True,
    ),
    ModelConfig(
        model=db.BlogPost,
        list_columns=["id", "slug", "title", "author_id", "created_at"],
        category=Category.BLOG,
    ),
    ModelConfig(
        model=db.Board,
        list_columns=["id", "slug", "title"],
        category=Category.DISCUSSION,
        read_only=True,
    ),
    ModelConfig(
        model=db.ContributorInfo,
        list_columns=["id", "name", "title"],
        category=Category.SITE,
        permission="moderator",
    ),
    ModelConfig(
        model=db.Dictionary,
        list_columns=["id", "slug", "title"],
        category=Category.DICTIONARIES,
        tasks=[
            Task(
                name="Import dictionaries",
                slug="import-dictionaries",
                handler=tasks.import_dictionaries,
            ),
        ],
        display_field="slug",
        search_key="slug",
    ),
    ModelConfig(
        model=db.DictionaryEntry,
        list_columns=["id", "dictionary_id", "key"],
        category=Category.DICTIONARIES,
        read_only=True,
        search_key="key",
    ),
    ModelConfig(
        model=db.Genre,
        list_columns=["id", "name"],
        category=Category.PROOFING,
        permission="moderator",
    ),
    ModelConfig(
        model=db.Page,
        list_columns=["id", "project_id", "slug", "order"],
        category=Category.PROOFING,
        read_only=True,
    ),
    ModelConfig(
        model=db.PageStatus,
        list_columns=["id", "name"],
        category=Category.PROOFING,
        read_only=True,
    ),
    ModelConfig(
        model=db.PasswordResetToken,
        list_columns=["id", "user_id"],
        category=Category.AUTH,
        read_only=True,
    ),
    ModelConfig(
        model=db.Post,
        list_columns=["id", "thread_id", "author_id", "created_at"],
        category=Category.DISCUSSION,
        read_only=True,
    ),
    ModelConfig(
        model=db.Project,
        list_columns=["id", "slug", "display_title", "creator_id"],
        category=Category.PROOFING,
        tasks=[
            Task(
                name="Import projects",
                slug="import-projects",
                handler=tasks.import_projects,
            ),
            Task(
                name="Export projects",
                slug="export-projects",
                handler=tasks.export_projects,
            ),
            Task(
                name="Regenerate pages",
                slug="regenerate-pages",
                handler=tasks.regenerate_pages,
            ),
        ],
        display_field="slug",
        enum_fields={"status": ProjectStatus},
        search_key="slug",
    ),
    ModelConfig(
        model=db.ProjectSponsorship,
        list_columns=["id", "sa_title", "en_title", "cost_inr"],
        category=Category.SITE,
        permission="moderator",
    ),
    ModelConfig(
        model=db.Revision,
        list_columns=["id", "page_id", "author_id", "created_at"],
        category=Category.PROOFING,
        read_only=True,
    ),
    ModelConfig(
        model=db.RevisionBatch,
        list_columns=["id", "user_id", "created_at"],
        category=Category.PROOFING,
        read_only=True,
    ),
    ModelConfig(
        model=db.Role,
        list_columns=["id", "name"],
        category=Category.AUTH,
        read_only=True,
    ),
    ModelConfig(
        model=db.Text,
        list_columns=["id", "slug", "title"],
        category=Category.TEXTS,
        tasks=[
            Task(
                name="Import texts",
                slug="import-text",
                handler=tasks.import_text,
            ),
            Task(
                name="Import parse data",
                slug="import-parse-data",
                handler=tasks.import_parse_data,
            ),
            Task(
                name="Import metadata",
                slug="import-metadata",
                handler=tasks.import_metadata,
            ),
            Task(
                name="Export metadata",
                slug="export-metadata",
                handler=tasks.export_metadata,
            ),
            Task(
                name="Add genre",
                slug="add-genre",
                handler=tasks.add_genre_to_texts,
            ),
            Task(
                name="Create exports",
                slug="create-exports",
                handler=tasks.create_exports,
            ),
            Task(
                name="Run quality report",
                slug="run-quality-report",
                handler=tasks.run_quality_reports,
            ),
            Task(
                name="Export text archive",
                slug="export-text-archive",
                handler=tasks.export_text_archive,
            ),
        ],
        display_field="slug",
        enum_fields={"status": TextStatus},
        search_key="slug",
    ),
    ModelConfig(
        model=db.TextBlock,
        list_columns=["id", "text_id", "slug", "n"],
        category=Category.TEXTS,
    ),
    ModelConfig(
        model=db.TextSection,
        list_columns=["id", "text_id", "slug", "title"],
        category=Category.TEXTS,
        read_only=True,
    ),
    ModelConfig(
        model=db.TextReport,
        list_columns=["id", "text_id", "created_at", "updated_at"],
        category=Category.TEXTS,
        read_only=True,
    ),
    ModelConfig(
        model=db.TextExport,
        list_columns=["id", "slug"],
        category=Category.TEXTS,
        tasks=[
            Task(
                name="Delete selected exports",
                slug="delete-exports",
                handler=tasks.delete_exports,
            ),
            Task(
                name="Save XML files to disk cache",
                slug="save-xml-to-disk-cache",
                handler=tasks.save_xml_to_disk_cache,
            ),
        ],
        search_key="slug",
    ),
    ModelConfig(
        model=db.TextCollection,
        list_columns=["id", "slug", "title", "parent_id", "order"],
        category=Category.TEXTS,
        display_field="title",
        tasks=[
            Task(
                name="Manage tree",
                slug="manage-tree",
                handler=lambda **kwargs: redirect(url_for("admin.manage_collections")),
            ),
            Task(
                name="Export collections",
                slug="export-collections",
                handler=tasks.export_collections,
            ),
            Task(
                name="Import collections",
                slug="import-collections",
                handler=tasks.import_collections,
            ),
        ],
    ),
    ModelConfig(
        model=db.Thread,
        list_columns=["id", "board_id", "title", "created_at"],
        category=Category.DISCUSSION,
        read_only=True,
    ),
    ModelConfig(
        model=db.Token,
        list_columns=["id", "form", "base", "parse", "block_id", "order"],
        category=Category.PARSE_DATA,
        read_only=True,
    ),
    ModelConfig(
        model=db.TokenBlock,
        list_columns=["id", "text_id", "block_id"],
        category=Category.PARSE_DATA,
        read_only=True,
    ),
    ModelConfig(
        model=db.TokenRevision,
        list_columns=["id", "token_block_id", "author_id"],
        category=Category.PARSE_DATA,
        read_only=True,
    ),
    ModelConfig(
        model=db.User,
        list_columns=["id", "username", "email", "created_at"],
        category=Category.AUTH,
        display_field="username",
        search_key="username",
    ),
]

MODELS = sorted([config.model.__name__ for config in MODEL_CONFIG])


def get_indexed_columns(model_class):
    inspector = inspect(model_class)
    indexed = set()
    for column in inspector.columns:
        if column.primary_key or column.index or column.unique:
            indexed.add(column.name)
        elif column.foreign_keys:
            indexed.add(column.name)
    if hasattr(model_class, "__table__"):
        for idx in model_class.__table__.indexes:
            if len(idx.columns) == 1:
                indexed.add(list(idx.columns)[0].name)
    return indexed


def get_foreign_key_info(model_class):
    inspector = inspect(model_class)
    fk_map = {}
    for column in inspector.columns:
        if column.foreign_keys:
            fk = list(column.foreign_keys)[0]
            target_table = fk.column.table.name
            target_model = None
            for config in MODEL_CONFIG:
                if config.model.__tablename__ == target_table:
                    target_model = config.model.__name__
                    break
            if target_model:
                fk_map[column.name] = target_model
    return fk_map


def get_many_to_many_info(model_class):
    mapper = inspect(model_class)
    m2m_info = {}

    for relationship in mapper.relationships:
        if relationship.secondary is not None:
            target_model = relationship.mapper.class_
            m2m_info[relationship.key] = target_model

    return m2m_info


def populate_model_attributes_from_form(obj, form, model_class):
    from datetime import datetime

    m2m_info = get_many_to_many_info(model_class)

    for field in form:
        if field.name in m2m_info:
            continue
        if hasattr(obj, field.name):
            value = field.data
            if field.type in ("DateTimeField", "DateTimeLocalField") and isinstance(
                value, str
            ):
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f",
                ]:
                    try:
                        value = datetime.strptime(value, fmt)
                        break
                    except (ValueError, TypeError):
                        continue
                else:
                    value = None
            setattr(obj, field.name, value)


def populate_model_m2m_from_form(obj, form, model_class, session):
    m2m_info = get_many_to_many_info(model_class)

    for rel_name, target_model_class in m2m_info.items():
        if not hasattr(form, rel_name):
            continue

        selected_ids = form[rel_name].data
        # Filter out empty strings and convert to integers
        id_list = [int(id_str) for id_str in selected_ids if id_str]

        # Fetch all related items in a single query
        if id_list:
            related_items = (
                session.query(target_model_class)
                .filter(target_model_class.id.in_(id_list))
                .all()
            )
        else:
            related_items = []

        setattr(obj, rel_name, related_items)


def create_model_form(model_class, obj=None):
    model_config = get_model_config(model_class.__name__)
    inspector = inspect(model_class)
    fields = {}

    for column in inspector.columns:
        col_name = column.name
        col_type = column.type

        if column.primary_key or col_name in ["created_at", "updated_at"]:
            continue

        field_kwargs = {"validators": [Optional()] if column.nullable else []}

        if column.foreign_keys:
            fk = list(column.foreign_keys)[0]
            target_table = fk.column.table.name
            target_model_class = None
            for config in MODEL_CONFIG:
                if config.model.__tablename__ == target_table:
                    target_model_class = config.model
                    break

            if target_model_class:
                session = q.get_session()
                choices = []
                if column.nullable:
                    choices.append(("", "-- None --"))
                for item in (
                    session.query(target_model_class).limit(FK_DROPDOWN_LIMIT).all()
                ):
                    choices.append((item.id, str(item)))

                def coerce_int_or_none(x):
                    if x == "" or x is None:
                        return None
                    return int(x)

                fields[col_name] = SelectField(
                    col_name,
                    choices=choices,
                    coerce=coerce_int_or_none,
                    **field_kwargs,
                )
                continue

        python_type = col_type.python_type
        if isinstance(col_type, JSON):
            fields[col_name] = TextAreaField(
                col_name,
                render_kw={"style": "font-family: monospace;", "rows": 10},
                **field_kwargs,
            )
        elif python_type == int:
            fields[col_name] = IntegerField(col_name, **field_kwargs)
        elif python_type == bool:
            fields[col_name] = BooleanField(col_name)
        elif python_type == str:
            enum_class = (
                model_config.enum_fields.get(col_name) if model_config else None
            )

            if enum_class:
                choices = []
                if column.nullable:
                    choices.append(("", "-- None --"))
                choices.extend([(e.value, e.value) for e in enum_class])
                fields[col_name] = SelectField(
                    col_name, choices=choices, **field_kwargs
                )
            elif isinstance(col_type, Text) or (
                hasattr(col_type, "length")
                and col_type.length
                and col_type.length > 255
            ):
                fields[col_name] = TextAreaField(col_name, **field_kwargs)
            else:
                fields[col_name] = StringField(col_name, **field_kwargs)
        else:
            from datetime import datetime, date

            if python_type in (datetime, date):
                fields[col_name] = DateTimeLocalField(
                    col_name, format="%Y-%m-%dT%H:%M:%S", **field_kwargs
                )
            else:
                fields[col_name] = StringField(col_name, **field_kwargs)

    m2m_info = get_many_to_many_info(model_class)
    session = q.get_session()

    for rel_name, target_model_class in m2m_info.items():
        choices = []
        for item in session.query(target_model_class).limit(200).all():
            choices.append((str(item.id), str(item)))

        default = []
        if obj:
            related_items = getattr(obj, rel_name, [])
            default = [str(item.id) for item in related_items]

        fields[rel_name] = SelectMultipleField(
            rel_name,
            choices=choices,
            default=default,
            render_kw={"size": "5"},
        )

    ModelForm = type(f"{model_class.__name__}Form", (FlaskForm,), fields)
    form = ModelForm(obj=obj) if obj else ModelForm()

    # Set manually for m2m fields since these aren't present as attributes on `obj`.
    # Only do this on GET requests - on POST, the form is populated from request data
    if obj and request.method == "GET":
        for rel_name in m2m_info.keys():
            if hasattr(form, rel_name):
                related_items = getattr(obj, rel_name, [])
                getattr(form, rel_name).data = [str(item.id) for item in related_items]

    return form


def get_models_by_category():
    from collections import defaultdict

    by_category = defaultdict(list)
    for config in MODEL_CONFIG:
        by_category[config.category].append(config)
    for category in by_category:
        by_category[category].sort(key=lambda c: c.model.__name__)
    return dict(sorted(by_category.items(), key=lambda x: x[0].value))


def get_model_config(model_name):
    return next((c for c in MODEL_CONFIG if c.model.__name__ == model_name), None)


@bp.before_request
def check_access():
    if request.endpoint == "admin.index":
        if not current_user.is_moderator:
            abort(404)
        return

    if request.endpoint in (
        "admin.celery_tasks",
        "admin.celery_task_detail",
        "admin.debug_memory",
        "admin.manage_collections",
        "admin.collections_save_tree",
        "admin.collections_create",
        "admin.collections_edit",
        "admin.collections_delete",
    ):
        if not current_user.is_admin:
            abort(404)
        return

    model_name = request.view_args.get("model_name") if request.view_args else None
    if not model_name:
        abort(404)

    config = get_model_config(model_name)
    if not config:
        abort(404)
    if config.permission == "admin" and not current_user.is_admin:
        abort(404)
    if config.permission == "moderator" and not current_user.is_moderator:
        abort(404)


@bp.route("/")
def index():
    """Admin dashboard."""
    return render_template(
        "admin/index.html",
        models=MODELS,
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        models_by_category=get_models_by_category(),
    )


@bp.route("/<model_name>/")
def list_model(model_name):
    """Model list view."""
    config = get_model_config(model_name)
    if not config:
        abort(404)

    model_class = config.model
    list_columns = config.list_columns
    tasks = config.tasks

    page = request.args.get("page", 1, type=int)
    sort = request.args.get("sort", "")
    sort_dir = request.args.get("sort_dir", "")
    search = request.args.get("search", "").strip()
    per_page = 50

    indexed_columns = get_indexed_columns(model_class)

    session = q.get_session()
    query = session.query(model_class)

    if search and config.search_key:
        search_col = getattr(model_class, config.search_key, None)
        if search_col is not None:
            query = query.filter(search_col.ilike(f"{search}%"))

    if sort and sort_dir in ("asc", "desc") and sort in indexed_columns:
        col = getattr(model_class, sort, None)
        if col is not None:
            query = query.order_by(col.asc() if sort_dir == "asc" else col.desc())

    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()

    total_pages = (total + per_page - 1) // per_page
    fk_map = get_foreign_key_info(model_class)

    # Build foreign key labels efficiently (single query per model type)
    fk_labels = {}
    display_fields = {
        config.model.__name__: config.display_field
        for config in MODEL_CONFIG
        if config.display_field
    }
    fk_by_model = {}
    for col, fk_model_name in fk_map.items():
        if fk_model_name in display_fields:
            fk_by_model.setdefault(fk_model_name, []).append(col)
    for fk_model_name, fk_columns in fk_by_model.items():
        display_field = display_fields[fk_model_name]
        fk_model_class = getattr(db, fk_model_name)
        ids = set()
        for col in fk_columns:
            ids.update(
                [
                    getattr(item, col)
                    for item in items
                    if hasattr(item, col) and getattr(item, col) is not None
                ]
            )

        if ids:
            # One query for foreign key IDs --> label
            results = (
                session.query(fk_model_class.id, getattr(fk_model_class, display_field))
                .filter(fk_model_class.id.in_(ids))
                .all()
            )

            label_map = {id_: label for id_, label in results}
            for col in fk_columns:
                fk_labels[col] = label_map

    template_vars = dict(
        model_name=model_name,
        models=MODELS,
        current_model=model_name,
        list_columns=list_columns,
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        fk_map=fk_map,
        fk_labels=fk_labels,
        tasks=tasks,
        read_only=config.read_only,
        indexed_columns=indexed_columns,
        sort=sort,
        sort_dir=sort_dir,
        search=search,
        search_key=config.search_key,
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        models_by_category=get_models_by_category(),
    )

    if request.args.get("partial"):
        html = render_template("admin/list_table.html", **template_vars)
        return jsonify(html=html, total=total)

    return render_template("admin/list.html", **template_vars)


@bp.route("/<model_name>/create", methods=["GET", "POST"])
def create_model(model_name):
    config = get_model_config(model_name)
    if not config or config.read_only:
        abort(404)

    model_class = config.model
    form = create_model_form(model_class)
    fk_map = get_foreign_key_info(model_class)

    if form.validate_on_submit():
        session = q.get_session()
        item = model_class()

        populate_model_attributes_from_form(item, form, model_class)
        session.add(item)

        # Flush to get the ID for many-to-many.
        try:
            session.flush()
        except (SQLAlchemyError, ValueError) as e:
            session.rollback()
            flash(f"Error creating {model_name}: {str(e)}", "error")
            return render_template(
                "admin/create.html",
                model_name=model_name,
                models=MODELS,
                current_model=model_name,
                form=form,
                fk_map=fk_map,
                model_configs={c.model.__name__: c for c in MODEL_CONFIG},
                models_by_category=get_models_by_category(),
            )

        populate_model_m2m_from_form(item, form, model_class, session)

        try:
            session.commit()
            flash(f"{model_name} created successfully", "success")
            return redirect(url_for("admin.list_model", model_name=model_name))
        except (SQLAlchemyError, ValueError) as e:
            session.rollback()
            flash(f"Error creating {model_name}: {str(e)}", "error")

    return render_template(
        "admin/create.html",
        model_name=model_name,
        models=MODELS,
        current_model=model_name,
        form=form,
        fk_map=fk_map,
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        models_by_category=get_models_by_category(),
    )


@bp.route("/<model_name>/<int:item_id>/edit", methods=["GET", "POST"])
def edit_model(model_name, item_id):
    config = get_model_config(model_name)
    if not config:
        abort(404)

    model_class = config.model

    session = q.get_session()
    item = session.get(model_class, item_id)
    if not item:
        abort(404)

    form = create_model_form(model_class, obj=item)
    fk_map = get_foreign_key_info(model_class)

    if form.validate_on_submit():
        if config.read_only:
            abort(404)

        populate_model_attributes_from_form(item, form, model_class)
        populate_model_m2m_from_form(item, form, model_class, session)

        try:
            session.commit()
            flash(f"{model_name} updated successfully", "success")
            return redirect(url_for("admin.list_model", model_name=model_name))
        except (SQLAlchemyError, ValueError) as e:
            session.rollback()
            flash(f"Error updating {model_name}: {str(e)}", "error")

    return render_template(
        "admin/edit.html",
        model_name=model_name,
        models=MODELS,
        current_model=model_name,
        form=form,
        item=item,
        item_id=item_id,
        read_only=config.read_only,
        fk_map=fk_map,
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        models_by_category=get_models_by_category(),
    )


@bp.route("/<model_name>/<int:item_id>/delete", methods=["POST"])
def delete_model(model_name, item_id):
    config = get_model_config(model_name)
    if not config:
        abort(404)

    model_class = config.model

    session = q.get_session()
    item = session.get(model_class, item_id)
    if not item:
        abort(404)

    try:
        session.delete(item)
        session.commit()
        flash(f"{model_name} deleted successfully", "success")
    except SQLAlchemyError as e:
        session.rollback()
        flash(f"Error deleting {model_name}: {str(e)}", "error")

    return redirect(url_for("admin.list_model", model_name=model_name))


@bp.route("/<model_name>/task/<task_slug>", methods=["GET", "POST"])
def run_task(model_name, task_slug):
    config = get_model_config(model_name)
    if not config:
        abort(404)

    task = next((t for t in config.tasks if t.slug == task_slug), None)
    if not task:
        abort(404)

    selected_ids = request.form.getlist("selected_ids")
    return task.handler(model_name=model_name, selected_ids=selected_ids)


@bp.route("/celery-tasks")
def celery_tasks():
    """Browse Celery task execution logs."""
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", "")
    per_page = 50

    session = q.get_session()
    query = session.query(db.CeleryTaskLog).order_by(db.CeleryTaskLog.id.desc())

    if status_filter:
        query = query.filter(db.CeleryTaskLog.status == status_filter)

    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "admin/celery-tasks.html",
        items=items,
        page=page,
        total=total,
        total_pages=total_pages,
        status_filter=status_filter,
        models_by_category=get_models_by_category(),
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        current_model=None,
    )


@bp.route("/celery-tasks/<int:task_log_id>")
def celery_task_detail(task_log_id):
    """View full details for a Celery task log entry."""
    session = q.get_session()
    item = session.get(db.CeleryTaskLog, task_log_id)
    if not item:
        abort(404)

    return render_template(
        "admin/celery-task-detail.html",
        item=item,
        models_by_category=get_models_by_category(),
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        current_model=None,
    )


_previous_type_counts = {}


@bp.route("/debug-memory")
def debug_memory():
    """Show memory usage breakdown for the current worker process.

    Hit this endpoint multiple times — the "growth" field shows which
    object types are increasing between calls, pointing to the leak.
    """
    import gc
    import os

    gc.collect()

    # RSS from /proc if available, else psutil
    rss_mb = None
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss_mb = int(line.split()[1]) / 1024
                    break
    except OSError:
        try:
            import psutil

            rss_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        except ImportError:
            pass

    # Single pass over gc.get_objects()
    from ambuda.models.base import Base as ModelBase

    type_counts = {}
    sa_counts = {}
    for obj in gc.get_objects():
        t = type(obj).__qualname__
        type_counts[t] = type_counts.get(t, 0) + 1
        if isinstance(obj, ModelBase):
            name = t
            sa_counts[name] = sa_counts.get(name, 0) + 1

    # Growth since last call
    global _previous_type_counts
    growth = {}
    if _previous_type_counts:
        for t, count in type_counts.items():
            prev = _previous_type_counts.get(t, 0)
            if count > prev:
                growth[t] = {"count": count, "delta": f"+{count - prev}"}
    growth = dict(sorted(growth.items(), key=lambda x: -int(x[1]["delta"][1:]))[:20])
    _previous_type_counts = type_counts

    top_types = dict(sorted(type_counts.items(), key=lambda x: -x[1])[:30])
    sa_counts = dict(sorted(sa_counts.items(), key=lambda x: -x[1])[:20])

    return jsonify(
        pid=os.getpid(),
        rss_mb=round(rss_mb, 1) if rss_mb else None,
        total_objects=sum(type_counts.values()),
        top_object_types=top_types,
        growth=growth,
        sqlalchemy_instances=sa_counts,
    )


# --- Collection management ---


def _collection_tree():
    """Build the full collection tree for the admin UI."""
    all_colls = q.Query(q.get_session()).all_collections()
    by_parent = q.group_collections_by_parent(all_colls)

    def build(parent_id):
        children = by_parent.get(parent_id, [])
        return [
            {
                "id": c.id,
                "slug": c.slug,
                "title": c.title,
                "order": c.order,
                "description": c.description or "",
                "children": build(c.id),
            }
            for c in children
        ]

    return build(None)


@bp.route("/collections")
def manage_collections():
    """Admin page for managing text collections with drag-and-drop."""
    tree = _collection_tree()
    return render_template(
        "admin/collections.html",
        tree=tree,
        models_by_category=get_models_by_category(),
        model_configs={c.model.__name__: c for c in MODEL_CONFIG},
        current_model="TextCollection",
    )


@bp.route("/collections/save-tree", methods=["POST"])
def collections_save_tree():
    """Save the full tree structure. Expects JSON: [{id, parent_id, order}, ...]."""
    data = request.get_json()
    items = data.get("items", [])
    if not items:
        return jsonify(ok=False, error="No items"), 400

    session = q.get_session()
    for item in items:
        coll = session.get(db.TextCollection, item["id"])
        if not coll:
            continue
        coll.parent_id = item.get("parent_id") or None
        coll.order = item.get("order", 0)
    session.commit()
    return jsonify(ok=True)


@bp.route("/collections/create", methods=["POST"])
def collections_create():
    """Create a new collection. Expects JSON: {slug, title, description, parent_id}."""
    data = request.get_json()
    slug = data.get("slug", "").strip()
    title = data.get("title", "").strip()
    if not slug or not title:
        return jsonify(ok=False, error="slug and title required"), 400

    session = q.get_session()

    existing = session.query(db.TextCollection).filter_by(slug=slug).first()
    if existing:
        return jsonify(ok=False, error="slug already exists"), 400

    parent_id = data.get("parent_id") or None
    max_order = (
        session.query(func.max(db.TextCollection.order))
        .filter(db.TextCollection.parent_id == parent_id)
        .scalar()
    ) or 0

    coll = db.TextCollection(
        slug=slug,
        title=title,
        description=data.get("description", "").strip() or None,
        parent_id=parent_id,
        order=max_order + 1,
    )
    session.add(coll)
    session.commit()
    return jsonify(ok=True, id=coll.id)


@bp.route("/collections/<int:collection_id>", methods=["PATCH"])
def collections_edit(collection_id):
    """Edit a collection's title, slug, or description. Expects JSON."""
    data = request.get_json()
    session = q.get_session()
    coll = session.get(db.TextCollection, collection_id)
    if not coll:
        return jsonify(ok=False, error="Not found"), 404

    if "title" in data:
        coll.title = data["title"].strip()
    if "slug" in data:
        new_slug = data["slug"].strip()
        existing = (
            session.query(db.TextCollection)
            .filter(
                db.TextCollection.slug == new_slug,
                db.TextCollection.id != collection_id,
            )
            .first()
        )
        if existing:
            return jsonify(ok=False, error="slug already exists"), 400
        coll.slug = new_slug
    if "description" in data:
        coll.description = data["description"].strip() or None

    session.commit()
    return jsonify(ok=True)


@bp.route("/collections/<int:collection_id>", methods=["DELETE"])
def collections_delete(collection_id):
    """Delete a collection. Its children are reparented to its parent."""
    session = q.get_session()
    coll = session.get(db.TextCollection, collection_id)
    if not coll:
        return jsonify(ok=False, error="Not found"), 404

    # Save target parent before deletion nullifies it via ORM cascade.
    new_parent_id = coll.parent_id

    # Reparent children to this collection's parent.
    # We must delete first because session.delete() triggers SQLAlchemy's
    # relationship cascade which sets child.parent_id = None.
    children = (
        session.query(db.TextCollection)
        .filter(db.TextCollection.parent_id == collection_id)
        .all()
    )
    session.delete(coll)
    session.flush()

    for child in children:
        child.parent_id = new_parent_id
    session.commit()
    return jsonify(ok=True)
