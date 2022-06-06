from flask import Flask

from ambuda import filters
from ambuda.views.dictionary import api
from ambuda.views.site import bp as site
from config import config


def create_app(config_name):
    app = Flask(__name__)

    # Config
    app.config.from_object(config[config_name])

    # Blueprints
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(site)

    # Filters
    app.jinja_env.filters.update(
        {
            "devanagari": filters.devanagari,
        }
    )

    return app
