"""Manages the auth/authentication data flow."""

from http import HTTPStatus
from typing import Optional

from flask import abort, redirect, request, url_for
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, login_url

from ambuda.database import User
from ambuda.queries import get_session


def _load_user(user_id: int) -> Optional[User]:
    session = get_session()
    return session.query(User).get(int(user_id))


def _unauthorized():
    if request.blueprint == "api":
        abort(HTTPStatus.UNAUTHORIZED)
    return redirect(url_for("auth.sign_in"))


def create_login_manager():
    login_manager = LoginManager()
    login_manager.user_loader(_load_user)

    return login_manager


def create_login_manager():
    login_manager = LoginManager()
    login_manager.user_loader(_load_user)
    login_manager.unauthorized_handler(_unauthorized)

    return login_manager
