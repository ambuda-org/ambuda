from flask import current_app, render_template, url_for
from flask_mail import Mail, Message

from ambuda import queries as q


mailer = Mail()


def send_reset_password_email(username: str, email: str, raw_token: str):
    msg = Message("Ambuda password reset link", recipients=[email])
    # FIXME: implementation without username?
    link = url_for(
        "auth.reset_password_from_token", username=username, raw_token=raw_token
    )
    msg.body = render_template("email/reset-password.txt", email=email, link=link)
    mailer.send(msg)
