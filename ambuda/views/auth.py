"""Authorization flow.

UX reference:

https://www.uxmatters.com/mt/archives/2018/09/signon-signoff-and-registration.php
"""

from flask import Blueprint, flash, render_template, redirect, url_for
from flask_login import current_user, login_user, logout_user, login_required
from flask_wtf import FlaskForm, RecaptchaField
from werkzeug.security import generate_password_hash
from wtforms import StringField, PasswordField
from wtforms import validators as val

import ambuda.queries as q
from ambuda import database as db


bp = Blueprint("auth", __name__)


# FIXME: redirect to site.index once user accounts are more useful.
POST_AUTH_ROUTE = "proofing.index"


class SignupForm(FlaskForm):
    username = StringField("Username", [val.Length(min=6, max=25), val.DataRequired()])
    password = PasswordField("Password", [val.Length(min=8), val.DataRequired()])
    email = StringField("Email", [val.DataRequired(), val.Email()])
    recaptcha = RecaptchaField()

    def validate_username(self, username):
        user = q.user(username.data)
        if user:
            raise val.ValidationError("Please use a different username.")

    def validate_email(self, email):
        session = q.get_session()
        user = session.query(db.User).filter_by(email=email.data).first()
        if user:
            raise val.ValidationError("Please use a different email address.")


class SignInForm(FlaskForm):
    username = StringField("Username", [val.Length(min=6, max=25), val.DataRequired()])
    password = PasswordField("Password", [val.Length(min=8), val.DataRequired()])


class RecoverForm(FlaskForm):
    password = PasswordField("Password", [val.Length(min=8), val.DataRequired()])


class ChangePasswordForm(FlaskForm):
    #: Old password. No validation requirements, in case we change our password
    #: criteria in the future.
    old_password = PasswordField("Old password", [val.DataRequired()])
    #: New password.
    new_password = PasswordField(
        "New password", [val.Length(min=8), val.DataRequired()]
    )


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("site.index"))

    form = SignupForm()
    if form.validate_on_submit():
        user = q.create_user(
            username=form.username.data,
            email=form.email.data,
            raw_password=form.password.data,
        )
        login_user(user, remember=True)
        return redirect(url_for(POST_AUTH_ROUTE))
    else:
        # Override the default message ("The response parameter is missing.")
        # for better UX.
        if form.recaptcha.errors:
            form.recaptcha.errors = ["Please click the reCAPTCHA box."]

        return render_template("auth/register.html", form=form)


@bp.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if current_user.is_authenticated:
        return redirect(url_for("site.index"))

    form = SignInForm()
    if form.validate_on_submit():
        user = q.user(form.username.data)
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            return redirect(url_for(POST_AUTH_ROUTE))
        else:
            flash("Invalid username or password.")
    return render_template("auth/sign-in.html", form=form)


@bp.route("/sign-out")
def sign_out():
    logout_user()
    return redirect(url_for(POST_AUTH_ROUTE))


@bp.route("/recover", methods=["GET", "POST"])
def recover():
    form = RecoverForm()
    return render_template("auth/recover.html", form=form)


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
