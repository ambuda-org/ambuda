from ambuda import create_app
from ambuda.mail import mailer
from flask_mail import Message

print("0")
app = create_app("development")
print("1")
mailer.init_app(app)

print("1.5")
with app.app_context():
    print("2")
    for i in range(10):
        msg = Message("Twilio SendGrid Test Email", recipients=["arun90@gmail.com"])
        print("3")
    msg.body = "This is a test email!"
    msg.html = "<p>This is a test email!</p>"

    print("4")
    mailer.send(msg)
    print("5")
