from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

import config
from ambuda import auth as auth_manager
from ambuda import filters
from ambuda.views.about import bp as about
from ambuda.views.auth import bp as auth
from ambuda.views.api import bp as api
from ambuda.views.cheda import bp as parses
from ambuda.views.dictionaries import bp as dictionaries

from ambuda.views.proofing import bp as proofing
from ambuda.views.site import bp as site
from ambuda.views.texts import bp as texts


def create_app(config_name: str):
    load_dotenv(".env")

    app = Flask(__name__)

    # Config
    app.config.from_object(config.config[config_name])

    # Extensions
    login_manager = auth_manager.create_login_manager()
    login_manager.init_app(app)

    # Blueprints
    app.register_blueprint(about, url_prefix="/about")
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)
    app.register_blueprint(dictionaries, url_prefix="/dictionaries")
    app.register_blueprint(parses, url_prefix="/parses")
    app.register_blueprint(proofing, url_prefix="/proofing")
    app.register_blueprint(site)
    app.register_blueprint(texts, url_prefix="/texts")

    # Filters
    app.jinja_env.filters.update(
        {
            "d": filters.devanagari,
            "devanagari": filters.devanagari,
            "roman": filters.roman,
        }
    )

    return app
