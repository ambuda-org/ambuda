from flask import Flask

from ambuda import filters
from ambuda.views.dictionary import api
from ambuda.views.site import bp as site


app = Flask(__name__)
app.register_blueprint(api, url_prefix="/api")
app.register_blueprint(site)
app.jinja_env.filters.update(
    {
        "devanagari": filters.devanagari,
    }
)
