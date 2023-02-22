"""Authorization flow.

UX reference:

https://www.uxmatters.com/mt/archives/2018/09/signon-signoff-and-registration.php

Security reference:
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html

Max lengths:
- https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html suggests 64 characters for password
- https://www.rfc-editor.org/errata_search.php?rfc=3696 specifies 254 characters for email address

"""

import secrets
from datetime import datetime, timedelta
from typing import Optional

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm, RecaptchaField
from wtforms import EmailField, PasswordField, StringField
from wtforms import validators as val

import ambuda.queries as q
from ambuda import database as db
from ambuda import mail

bp = Blueprint("auth", __name__)

# maximum lengths of authentication fields
MIN_EMAIL_ADDRESS_LEN = 4
MAX_EMAIL_ADDRESS_LEN = 254
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 256
MIN_USERNAME_LEN= 6
MAX_USERNAME_LEN = 64

# token lifetime
MAX_TOKEN_LIFESPAN_IN_HOURS = 24
# FIXME: redirect to site.index once user accounts are more useful.
POST_AUTH_ROUTE = "proofing.index"


def _create_reset_token(user_id) -> str:
    raw_token = secrets.token_urlsafe()

    session = q.get_session()
    record = db.PasswordResetToken(user_id=user_id, is_active=True)
    record.set_token(raw_token)
    session.add(record)
    session.commit()

    return raw_token


def _get_reset_token_for_user(user_id: int) -> Optional[db.PasswordResetToken]:
    # User might have requested multiple tokens -- get the latest one.
    session = q.get_session()
    return (
        session.query(db.PasswordResetToken)
        .filter_by(user_id=user_id, is_active=True)
        .order_by(db.PasswordResetToken.created_at.desc())
        .first()
    )


def _is_valid_reset_token(row: db.PasswordResetToken, raw_token: str, now=None):
    now = now or datetime.utcnow()

    # No token for user
    if not row:
        return False

    # Deactivated
    if not row.is_active:
        return False

    # Token too old
    max_age = timedelta(hours=MAX_TOKEN_LIFESPAN_IN_HOURS)
    if row.created_at + max_age <= now:
        return False

    # Token mismatch
    if not row.check_token(raw_token):
        return False

    return True


def get_field_validators(field_name: str, min_len: int, max_len: int):
    return [
        val.DataRequired(),
        val.Length(min=min_len, max=max_len, message=f"{field_name.capitalize()} must be between {min_len} and {max_len} characters long"),
    ]

class SignupForm(FlaskForm):
    username = StringField(_l("Username"), [*get_field_validators("username", MIN_USERNAME_LEN, MAX_USERNAME_LEN),
                                            val.Regexp('^[^\s]*$', message="Username must not contain spaces"), 
                                            ]
    )
    password = PasswordField(_l("Password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])
    email = StringField(_l("Email address"), [*get_field_validators("email address", MIN_EMAIL_ADDRESS_LEN, MAX_EMAIL_ADDRESS_LEN),
                                              val.Email(),
                                             ]
    )
    recaptcha = RecaptchaField()

    def validate_username(self, username):
        # username is case insensitive
        user = q.user(username.data.lower())
        if user:
            raise val.ValidationError("Please use a different username.")

    def validate_email(self, email):
        session = q.get_session()
        # email is case insensitive
        user = session.query(db.User).filter_by(email=email.data.lower()).first()
        if user:
            raise val.ValidationError("Please use a different email address.")


class SignInForm(FlaskForm):
    username = StringField(_l("Username"), [*get_field_validators("username", MIN_USERNAME_LEN, MAX_USERNAME_LEN), 
                                            val.Regexp('^[^\s]*$', message="Username must not contain spaces"),
                                            ]
    )
    password = PasswordField(_l("Password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])


class ResetPasswordForm(FlaskForm):
    email = EmailField("Email", [*get_field_validators("email address", MIN_EMAIL_ADDRESS_LEN, MAX_EMAIL_ADDRESS_LEN),
                                 val.Email(),
                                ]
    )
    recaptcha = RecaptchaField()


class ChangePasswordForm(FlaskForm):
    #: Old password. No validation requirements, in case we change our password
    #: criteria in the future.
    old_password = PasswordField(_l("Old password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])
    #: New password.
    new_password = PasswordField(_l("New password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])


class ResetPasswordFromTokenForm(FlaskForm):
    password = PasswordField(_l("Password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])
    confirm_password = PasswordField(_l("Confirm password"), [*get_field_validators("password", MIN_PASSWORD_LEN, MAX_PASSWORD_LEN)])


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        logout_if_not_ok()
        return redirect(url_for("site.index"))

    form = SignupForm()
    # save username and email in lowercase
    if form.validate_on_submit():
        user = q.create_user(
            username=form.username.data.lower(),
            email=form.email.data.lower(),
            raw_password=form.password.data,
        )
        login_user(user, remember=True)
        return redirect(url_for(POST_AUTH_ROUTE))
    else:
        # Override the default message ("The response parameter is missing.")
        # for better UX.
        if form.recaptcha.errors:
            form.recaptcha.errors = [_l("Please click the reCAPTCHA box.")]

        return render_template("auth/register.html", form=form)


@bp.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if current_user.is_authenticated:
        logout_if_not_ok()
        return redirect(url_for("site.index"))

    form = SignInForm()
    # username check is case insensitive
    if form.validate_on_submit():
        user = q.user(form.username.data.lower())
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            return redirect(url_for(POST_AUTH_ROUTE))
        else:
            flash("Invalid username or password.")
    return render_template("auth/sign-in.html", form=form)


def logout_if_not_ok():
    # Check if user is now deleted or banned
    user = q.user(username=current_user.username)
    if user and not user.is_ok:
        logout_user()


@bp.route("/sign-out")
def sign_out():
    logout_user()
    return redirect(url_for(POST_AUTH_ROUTE))


@bp.route("/reset-password", methods=["GET", "POST"])
def get_reset_password_token():
    """Email the user a password reset link."""
    form = ResetPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower()
        session = q.get_session()
        user = session.query(db.User).filter_by(email=email).first()
        if user:
            raw_token = _create_reset_token(user.id)
            mail.send_reset_password_link(
                username=user.username, email=user.email, raw_token=raw_token
            )
            return render_template("auth/reset-password-post.html", email=user.email)
        else:
            flash(
                "Sorry, the email address you provided is not associated with any of our acounts."
            )

    # Override the default message ("The response parameter is missing.")
    # for better UX.
    if form.recaptcha.errors:
        form.recaptcha.errors = ["Please click the reCAPTCHA box."]

    return render_template("auth/reset-password.html", form=form)


@bp.route("/reset-password/<username>/<raw_token>", methods=["GET", "POST"])
def reset_password_from_token(username, raw_token):
    """Reset password after the user clicks a reset link."""
    msg_invalid = "Sorry, this reset password link isn't valid. Please try again."

    user = q.user(username.lower())
    if user is None:
        flash(msg_invalid)
        return redirect(url_for("auth.get_reset_password_token"))

    token = _get_reset_token_for_user(user.id)
    if not _is_valid_reset_token(token, raw_token):
        flash(msg_invalid)
        return redirect(url_for("auth.get_reset_password_token"))

    form = ResetPasswordFromTokenForm()
    if form.validate_on_submit():
        has_password_match = form.password.data == form.confirm_password.data
        if has_password_match:
            user.set_password(form.password.data)
            token.is_active = False
            token.used_at = datetime.now()

            session = q.get_session()
            session.add(user)
            session.add(token)
            session.commit()

            # Expire any existing sessions.
            logout_user()
            flash("Successfully reset password!", "success")
            mail.send_confirm_reset_password(
                username=user.username,
                email=user.email,
            )
            return redirect(url_for("auth.sign_in"))

        if not has_password_match:
            form.password.errors.append("Passwords must match.")

    return render_template(
        "auth/reset-password-from-token.html", username=user.username, form=form
    )


@bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if not form.validate_on_submit():
        return render_template("auth/change-password.html", form=form)

    if current_user.check_password(form.old_password.data):
        session = q.get_session()
        current_user.set_password(form.new_password.data)
        session.add(current_user)
        session.commit()

        flash("Changed password successfully!", "success")
        return redirect(url_for("proofing.user", username=current_user.username))
    else:
        flash("Old password isn't valid.")

    return render_template("auth/change-password.html", form=form)
