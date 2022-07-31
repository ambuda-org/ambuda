from flask import render_template, flash, url_for, make_response, request, Blueprint
from flask_login import login_required
from flask_wtf import FlaskForm
from markupsafe import escape, Markup
from werkzeug.exceptions import abort
from werkzeug.utils import redirect
from wtforms import StringField
from wtforms.validators import DataRequired

from ambuda import queries as q, database as db
from ambuda.utils import proofing_utils


bp = Blueprint("projects", __name__)


class EditMetadataForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    author = StringField("Author")
    editor = StringField("Editor")
    publisher = StringField("Publisher")
    publication_year = StringField("Publication year")


class SearchForm(FlaskForm):
    class Meta:
        csrf = False

    query = StringField("Query", validators=[DataRequired()])


@bp.route("/<slug>/")
def summary(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    session = q.get_session()
    recent_revisions = (
        session.query(db.Revision)
        .filter_by(project_id=project_.id)
        .order_by(db.Revision.created.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "proofing/projects/summary.html",
        project=project_,
        recent_revisions=recent_revisions,
    )


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug):
    project_ = q.project(slug)
    form = EditMetadataForm(obj=project_)

    if form.validate_on_submit():
        session = q.get_session()
        form.populate_obj(project_)
        session.commit()

        flash("Saved changes.", "success")
        return redirect(url_for("proofing.projects.summary", slug=slug))

    return render_template(
        "proofing/projects/edit.html",
        project=project_,
        form=form,
    )


@bp.route("/<slug>/download/")
def download(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    return render_template("proofing/projects/download.html", project=project_)


@bp.route("/<slug>/download/text")
def download_as_text(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    content_blobs = [
        p.revisions[-1].content if p.revisions else "" for p in project_.pages
    ]
    raw_text = proofing_utils.to_plain_text(content_blobs)

    response = make_response(raw_text, 200)
    response.mimetype = "text/plain"
    return response


@bp.route("/<slug>/download/xml")
def download_as_xml(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    project_meta = {
        "title": project_.title,
        "author": project_.author,
        "publication_year": project_.publication_year,
        "publisher": project_.publisher,
        "editor": project_.editor,
    }
    project_meta = {k: v or "TODO" for k, v in project_meta.items()}
    content_blobs = [
        p.revisions[-1].content if p.revisions else "" for p in project_.pages
    ]
    xml_blob = proofing_utils.to_tei_xml(project_meta, content_blobs)

    response = make_response(xml_blob, 200)
    response.mimetype = "text/xml"
    return response


@bp.route("/<slug>/search")
@login_required
def search(slug):
    project_ = q.project(slug)
    if project_ is None:
        abort(404)

    form = SearchForm(request.args)
    if not form.validate():
        return render_template(
            "proofing/projects/search.html", project=project_, form=form
        )

    query = form.query.data
    results = []
    for page_ in project_.pages:
        if not page_.revisions:
            continue

        matches = []

        latest = page_.revisions[-1]
        for line in latest.content.splitlines():
            if query in line:
                print(escape(line))
                matches.append(
                    {
                        "text": escape(line).replace(
                            query, Markup(f"<mark>{escape(query)}</mark>")
                        ),
                    }
                )
                print(matches[-1])
        if matches:
            results.append(
                {
                    "slug": page_.slug,
                    "matches": matches,
                }
            )
    return render_template(
        "proofing/projects/search.html",
        project=project_,
        form=form,
        query=query,
        results=results,
    )
