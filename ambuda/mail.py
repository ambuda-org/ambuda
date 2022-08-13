from flask import current_app, render_template
from flask_mail import Mail, Message

from ambuda import queries as q


mailer = Mail()


def send_reset_password_email(username: str, email: str):
    msg = Message("Ambuda password reset link", recipients=[email])
    link = "foo"
    msg.body = render_template("email/reset-password.txt", email=email, link=link)
    mailer.send(msg)
