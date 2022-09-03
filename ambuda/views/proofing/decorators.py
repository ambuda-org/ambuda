from functools import wraps
from typing import Callable

from flask import current_app, flash, redirect, url_for
from flask_login import current_user

from ambuda.enums import SiteRole


def p2_required(func: Callable):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.has_role(SiteRole.P2):
            flash("Sorry, you aren't authorized to use this feature.")
            return redirect(url_for("proofing.index"))
        return current_app.ensure_sync(func)(*args, **kwargs)

    return decorated_view


def moderator_required(func: Callable):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.has_role(SiteRole.MODERATOR):
            flash("Sorry, you aren't authorized to use this feature.")
            return redirect(url_for("proofing.index"))
        return current_app.ensure_sync(func)(*args, **kwargs)

    return decorated_view
