from flask import Flask

from ambuda import filters
from ambuda.views.dictionaries import api, bp as dictionaries
from ambuda.views.site import bp as site
from ambuda.views.texts import bp as texts
from config import config


def create_app(config_name):
    app = Flask(__name__)

    # Config
    app.config.from_object(config[config_name])

    # Blueprints
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(dictionaries, url_prefix="/dictionaries")
    app.register_blueprint(texts, url_prefix="/texts")
    app.register_blueprint(site)

    # Filters
    app.jinja_env.filters.update(
        {
            "devanagari": filters.devanagari,
            "roman": filters.roman,
            "sa_roman": filters.sa_roman,
        }
    )

    return app
