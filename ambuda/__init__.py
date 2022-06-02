from flask import Flask

from ambuda.views import bp


app = Flask(__name__)
app.register_blueprint(bp)

