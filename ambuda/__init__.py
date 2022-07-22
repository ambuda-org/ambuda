import os
from pathlib import Path

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask
from sentry_sdk.integrations.flask import FlaskIntegration

import config
from ambuda import auth as auth_manager
from ambuda import admin as admin_manager
from ambuda import filters
from ambuda.views.about import bp as about
from ambuda.views.auth import bp as auth
from ambuda.views.api import bp as api
from ambuda.views.cheda import bp as parses
from ambuda.views.dictionaries import bp as dictionaries
from ambuda.views.proofing import bp as proofing
from ambuda.views.site import bp as site
from ambuda.views.texts import bp as texts


def _initialize_sentry():
    """Initialize basic monitoring."""
    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn is None:
        print("Sentry is misconfigured -- skipping setup.")
        return

    sentry_sdk.init(
        dsn=sentry_dsn, integrations=[FlaskIntegration()], traces_sample_rate=0
    )


def create_app(config_name: str):
    load_dotenv(".env")
    if config_name == "production":
        _initialize_sentry()

    app = Flask(__name__)

    # Config
    app.config.from_object(config.config[config_name])

    # Extensions
    login_manager = auth_manager.create_login_manager()
    login_manager.init_app(app)

    with app.app_context():
        admin = admin_manager.create_admin_manager(app)

    # Blueprints
    app.register_blueprint(about, url_prefix="/about")
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)
    app.register_blueprint(dictionaries, url_prefix="/tools/dictionaries")
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
