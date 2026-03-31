import logging
import sys

import sentry_sdk
from dotenv import load_dotenv
from flask import Flask, session
from flask_babel import Babel, pgettext
from flask_caching import Cache
from sentry_sdk.integrations.flask import FlaskIntegration
from sqlalchemy import exc

import config
from ambuda import auth as auth_manager
from ambuda import checks, filters, queries
from ambuda.consts import LOCALES
from ambuda.mail import mailer
from ambuda.rate_limit import limiter
from ambuda.utils import assets
from ambuda.utils.json_serde import AmbudaJSONEncoder
from ambuda.utils.url_converters import ListConverter
from ambuda.views.about import bp as about
from ambuda.views.admin import bp as admin
from ambuda.views.api import bp as api
from ambuda.views.auth import bp as auth
from ambuda.views.bharati import bp as bharati
from ambuda.views.blog import bp as blog
from ambuda.views.dictionaries import bp as dictionaries
from ambuda.views.proofing import bp as proofing
from ambuda.views.proofing import user_bp as users
from ambuda.views.reader.authors import bp as authors
from ambuda.views.reader.collections import bp as collections
from ambuda.views.reader.parses import bp as parses
from ambuda.views.texts import bp as texts
from ambuda.views.catalog import bp as catalog
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

    if config_name == config.Env.PRODUCTION:
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
    config_spec = config.load_config_object(config_env)

    # Initialize Sentry monitoring only in production so that our Sentry page
    # contains only production warnings (as opposed to dev warnings).
    #
    # "Configuration should happen as early as possible in your application's
    # lifecycle." -- Sentry docs
    if config_env == config.Env.PRODUCTION:
        _initialize_sentry(config_spec.SENTRY_DSN)

    app = Flask(__name__)

    # Config
    app.config.from_object(config_spec)

    # Sanity checks
    assert config_env == config_spec.AMBUDA_ENVIRONMENT
    if config_env != config.Env.TESTING:
        with app.app_context():
            checks.check_database_uri(config_spec.SQLALCHEMY_DATABASE_URI)

    # Logger
    _initialize_logger(config_spec.LOG_LEVEL)

    # Database
    _initialize_db_session(app, config_env)

    # A custom Babel locale_selector.
    def get_locale():
        return session.get("locale", config_spec.BABEL_DEFAULT_LOCALE)

    # Extensions
    Babel(app, locale_selector=get_locale)

    login_manager = auth_manager.create_login_manager()
    login_manager.init_app(app)

    mailer.init_app(app)
    limiter.init_app(app)

    cache = Cache(
        app, config={"CACHE_TYPE": "FileSystemCache", "CACHE_DIR": "/tmp/ambuda-cache"}
    )
    app.cache = cache

    # Route extensions
    app.url_map.converters["list"] = ListConverter

    # Blueprints
    app.register_blueprint(authors, url_prefix="/authors")
    app.register_blueprint(collections, url_prefix="/collections")
    app.register_blueprint(about, url_prefix="/about")
    app.register_blueprint(admin, url_prefix="/admin")
    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(auth)
    app.register_blueprint(bharati, url_prefix="/bharati")
    app.register_blueprint(blog, url_prefix="/blog")
    app.register_blueprint(catalog, url_prefix="/texts/catalog")
    app.register_blueprint(dictionaries, url_prefix="/tools/dictionaries")
    app.register_blueprint(parses, url_prefix="/parses")
    app.register_blueprint(proofing, url_prefix="/proofing")
    app.register_blueprint(site)
    app.register_blueprint(texts, url_prefix="/texts")
    app.register_blueprint(users, url_prefix="/users")

    # Debug-only routes for local development.
    if app.debug or config.Env.TESTING:
        from ambuda.views.debug import bp as debug_bp
        from ambuda.views.ocr_eval import bp as ocr_eval_bp

        app.register_blueprint(debug_bp, url_prefix="/debug")
        app.register_blueprint(ocr_eval_bp, url_prefix="/debug/ocr-eval")

    # i18n string trimming
    app.jinja_env.policies["ext.i18n.trimmed"] = True
    # Template functions and filters
    app.jinja_env.filters.update(
        {
            "d": filters.devanagari,
            "slp2dev": filters.slp_to_devanagari,
            "devanagari": filters.devanagari,
            "hk_to_user_script": filters.hk_to_user_script,
            "hk_slug_to_user_script": filters.hk_slug_to_user_script,
            "devanagari_to_user_script": filters.devanagari_to_user_script,
            "roman": filters.roman,
            "markdown": filters.markdown,
            "time_ago": filters.time_ago,
            "human_readable_bytes": filters.human_readable_bytes,
            "reject_keys": filters.reject_keys,
        }
    )
    app.jinja_env.globals.update(
        {
            "asset": assets.hashed_static,
            "pgettext": pgettext,
            "ambuda_locales": LOCALES,
        }
    )

    app.json_encoder = AmbudaJSONEncoder

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://plausible.io https://cdn.jsdelivr.net https://unpkg.com https://donorbox.org https://www.google.com/recaptcha/ https://www.gstatic.com/recaptcha/; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https: ; "
            "frame-src https://donorbox.org https://www.google.com/recaptcha/; "
            "connect-src 'self' https://plausible.io; "
            "font-src 'self' https://fonts.gstatic.com; "
            "object-src 'none'; "
            "base-uri 'self'"
        )
        if config_env == config.Env.PRODUCTION:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    return app
