from collections.abc import Callable
from functools import wraps

from flask import current_app
from flask_login import current_user


def admin_required(func: Callable):
    """Allow access only to administrators.

    Adapted from `flask_login.utils.login_required`.
    """

    @wraps(func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_admin:
            return current_app.login_manager.unauthorized()
        return current_app.ensure_sync(func)(*args, **kwargs)

    return decorated_view
