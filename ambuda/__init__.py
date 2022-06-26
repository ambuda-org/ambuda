from flask import Flask

from ambuda import filters
from ambuda.views.api import bp as api
from ambuda.views.dictionaries import bp as dictionaries
from ambuda.views.site import bp as site
from ambuda.views.cheda import bp as parses
from ambuda.views.texts import bp as texts
from config import config


def create_app(config_name: str):
    app = Flask(__name__)

    # Config
    app.config.from_object(config[config_name])

    # Blueprints
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(dictionaries, url_prefix="/dictionaries")
    app.register_blueprint(parses, url_prefix="/parses")
    app.register_blueprint(texts, url_prefix="/texts")
    app.register_blueprint(site)

    # Filters
    app.jinja_env.filters.update(
        {
            "d": filters.devanagari,
            "devanagari": filters.devanagari,
            "roman": filters.roman,
        }
    )

    return app
