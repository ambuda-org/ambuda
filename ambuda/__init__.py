"""Main entrypoint for the Ambuda application.

For a high-level overview of the application and how to operate it, see:

https://ambuda.readthedocs.io/en/latest/
"""

import logging
import sys

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, session
from flask_babel import Babel, Domain
from sentry_sdk.integrations.flask import FlaskIntegration
from sqlalchemy import exc

import config
from ambuda import admin as admin_manager
from ambuda import auth as auth_manager
from ambuda import checks, filters, queries
from ambuda.mail import mailer
from ambuda.utils import assets
from ambuda.views.about import bp as about
from ambuda.views.api import bp as api
from ambuda.views.auth import bp as auth
from ambuda.views.dictionaries import bp as dictionaries
from ambuda.views.proofing import bp as proofing
from ambuda.views.reader.parses import bp as parses
from ambuda.views.reader.texts import bp as texts
from ambuda.views.site import bp as site


def _initialize_sentry(sentry_dsn: str):
    """Initialize basic monitoring through the third-party Sentry service."""
    sentry_sdk.init(
        dsn=sentry_dsn, integrations=[FlaskIntegration()], traces_sample_rate=0
    )


def _initialize_db_session(app, config_name: str):
    """Ensure that our SQLAlchemy session behaves well.

    The Flask-SQLAlchemy library manages all of this boilerplate for us
    automatically, but Flask-SQLAlchemy has relatively poor support for using
    our models outside of the application context, e.g. when running seed
    scripts or other batch jobs. So instead of using that extension, we manage
    the boilerplate ourselves.
    """

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Reset session state to prevent caching and memory leaks."""
        queries.get_session_class().remove()

    if config_name == config.PRODUCTION:
        # The hook below hides database errors. So, install the hook only if
        # we're in production.

        @app.errorhandler(exc.SQLAlchemyError)
        def handle_db_exceptions(error):
            """Rollback errors so that the db can handle future requests."""
            session = queries.get_session()
            session.rollback()


def _initialize_logger(log_level: int) -> None:
    """Initialize a simple logger for all requests."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s")
    )
    logging.getLogger().setLevel(log_level)
    logging.getLogger().addHandler(handler)


def create_app(config_env: str):
    """Initialize the Ambuda application."""

    # We store all env variables in a `.env` file so that it's easier to manage
    # different configurations.
    load_dotenv(".env")
    config_spec = config.load_config_object(config_env)

    # Initialize Sentry monitoring only in production so that our Sentry page
    # contains only production warnings (as opposed to dev warnings).
    #
    # "Configuration should happen as early as possible in your application's
    # lifecycle." -- Sentry docs
    if config_env == config.PRODUCTION:
        _initialize_sentry(config_spec.SENTRY_DSN)

    app = Flask(__name__)

    # Config
    app.config.from_object(config_spec)

    # Sanity checks
    if config_env != config.TESTING:
        with app.app_context():
            checks.check_database(config_spec.SQLALCHEMY_DATABASE_URI)

    # Logger
    _initialize_logger(config_spec.LOG_LEVEL)

    # Database
    _initialize_db_session(app, config_env)

    # Extensions
    babel = Babel(app)
    i18n_text = Domain(domain="text")

    @babel.localeselector
    def get_locale():
        return session.get("locale", config_spec.BABEL_DEFAULT_LOCALE)

    login_manager = auth_manager.create_login_manager()
    login_manager.init_app(app)

    mailer.init_app(app)

    with app.app_context():
        _ = admin_manager.create_admin_manager(app)

    # Blueprints
    app.register_blueprint(about, url_prefix="/about")
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)
    app.register_blueprint(dictionaries, url_prefix="/tools/dictionaries")
    app.register_blueprint(parses, url_prefix="/parses")
    app.register_blueprint(proofing, url_prefix="/proofing")
    app.register_blueprint(site)
    app.register_blueprint(texts, url_prefix="/texts")

    # i18n string trimming
    app.jinja_env.policies["ext.i18n.trimmed"] = True
    # Template functions and filters
    app.jinja_env.filters.update(
        {
            "d": filters.devanagari,
            "slp2dev": filters.slp_to_devanagari,
            "devanagari": filters.devanagari,
            "roman": filters.roman,
            "markdown": filters.markdown,
            "time_ago": filters.time_ago,
        }
    )
    app.jinja_env.globals.update(
        {
            "asset": assets.hashed_static,
            "pgettext": i18n_text.pgettext,
        }
    )

    return app
