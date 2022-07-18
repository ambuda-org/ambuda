"""Authorization flow.

UX reference: https://www.uxmatters.com/mt/archives/2018/09/signon-signoff-and-registration.php
"""

from flask import Blueprint, flash, render_template, redirect, url_for
from flask_login import current_user, login_user, logout_user
from flask_wtf import FlaskForm, RecaptchaField
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
            flash("Invalid username or password")
    return render_template("auth/sign-in.html", form=form)


@bp.route("/sign-out")
def sign_out():
    logout_user()
    return redirect(url_for(POST_AUTH_ROUTE))
