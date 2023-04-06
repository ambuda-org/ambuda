"""Manages an internal admin view for site data."""

from flask import abort
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib import sqla
from flask_login import current_user

import ambuda.database as db
import ambuda.queries as q


class AmbudaIndexView(AdminIndexView):
    @expose("/")
    def index(self):
        if not current_user.is_moderator:
            # Abort so that a malicious scraper can't infer that there's an
            # interesting page here.
            abort(404)
        return super().index()


class BaseView(sqla.ModelView):
    """Base view for models.

    By default, only admins can see model data.
    """

    def is_accessible(self):
        return current_user.is_admin

    def inaccessible_callback(self, name, **kw):
        abort(404)


class ModeratorBaseView(sqla.ModelView):
    """Base view for models that moderators are allowed to access."""

    def is_accessible(self):
        return current_user.is_moderator

    def inaccessible_callback(self, name, **kw):
        abort(404)


class UserView(BaseView):
    column_list = form_columns = ["username", "email"]
    can_delete = False


class TextBlockView(BaseView):
    column_list = form_columns = ["text", "slug", "xml"]


class TextView(BaseView):
    column_list = form_columns = ["slug", "title"]

    form_widget_args = {"header": {"readonly": True}}


class ProjectView(BaseView):
    column_list = ["slug", "title", "creator"]
    form_excluded_columns = ["creator", "board", "pages", "created_at", "updated_at"]


class DictionaryView(BaseView):
    column_list = form_columns = ["slug", "title"]


class SponsorshipView(ModeratorBaseView):
    column_labels = dict(
        sa_title="Sanskrit title",
        en_title="English title",
        cost_inr="Estimated cost (INR)",
    )
    create_template = "admin/sponsorship_create.html"
    edit_template = "admin/sponsorship_edit.html"


class ProoferBiographyView(ModeratorBaseView):
    create_template = "admin/sponsorship_create.html"
    edit_template = "admin/sponsorship_edit.html"


def create_admin_manager(app):
    session = q.get_session_class()
    admin = Admin(
        app,
        name="Ambuda",
        index_view=AmbudaIndexView(),
        base_template="admin/master.html",
    )

    admin.add_view(DictionaryView(db.Dictionary, session))
    admin.add_view(ProjectView(db.Project, session))
    admin.add_view(TextBlockView(db.TextBlock, session))
    admin.add_view(TextView(db.Text, session))
    admin.add_view(UserView(db.User, session))
    admin.add_view(SponsorshipView(db.ProjectSponsorship, session))
    admin.add_view(ProoferBiographyView(db.ProoferBiography, session))

    return admin
