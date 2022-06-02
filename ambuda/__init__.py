from flask import Flask

from ambuda import filters
from ambuda.views import bp


app = Flask(__name__)
app.register_blueprint(bp)
app.jinja_env.filters.update({
    'devanagari': filters.devanagari,
})
