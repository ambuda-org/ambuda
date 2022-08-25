from flask import render_template, url_for
from flask_mail import Mail, Message

mailer = Mail()


def send_reset_password_link(username: str, email: str, raw_token: str):
    msg = Message("[Ambuda] Please reset your password", recipients=[email])
    # FIXME: implementation without username?
    link = url_for(
        "auth.reset_password_from_token", username=username, raw_token=raw_token
    )
    msg.body = render_template(
        "email/reset-password-link.txt", username=username, link=link
    )
    mailer.send(msg)


def send_confirm_reset_password(username: str, email: str):
    msg = Message("[Ambuda] Your password was reset", recipients=[email])
    msg.body = render_template("email/confirm-reset-password.txt", username=username)
    mailer.send(msg)
