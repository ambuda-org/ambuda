"""Config management for the Ambuda Flask app.

All of Ambuda's interesting config values are defined in the project's `.env`
file. Here, we parse that file and map its values to specific config objects,
which we then load into Flask.

Most config values are documented on :class:`BaseConfig`, from which all other
classes inherit. Production-specific config values, which are mainly replated
to deployment, are defined on :class:`ProductionConfig`.

It's considered a best practice to keep this module outside the application
package: From the Flask docs (emphasis added):

    Configuration becomes more useful if you can store it in a separate file,
    *ideally located outside the actual application package*.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from flask import Flask


# Load dotenv early so that `_env` will work in the class definitions below.
load_dotenv()

#: The test environment. For unit tests only.
TESTING = "testing"
#: The development environment. For local development.
DEVELOPMENT = "development"
#: The production environment. For production serving.
PRODUCTION = "production"


def _make_path(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env(key: str, default=None) -> Optional[str]:
    """Fetch a value from the local environment.

    :param key: the envvar to fetch
    """
    return os.environ.get(key, default)


class BaseConfig:
    """Base settings for all configs."""

    # Core settings
    # -------------

    #: The Flask app environment ("production", "development", etc.). We set
    #: this explicitly so that Celery can have access to it and load an
    #: appropriate application context.
    AMBUDA_ENVIRONMENT = None

    #: Internal secret key for encrypting sensitive data.
    SECRET_KEY = _env("SECRET_KEY")

    #: URI for the Ambuda database. This URI (also called a URL in some docs)
    #: has the following basic format:
    #:
    #:     dialect+driver://username:password@host:port/database
    #:
    #: For more information, see:
    #:
    #: https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls
    SQLALCHEMY_DATABASE_URI = _env("SQLALCHEMY_DATABASE_URI")

    #: Where to store user uploads (PDFs, images, etc.).
    UPLOAD_FOLDER = _env("FLASK_UPLOAD_FOLDER")

    # Extensions
    # ----------

    #: If True, enable cross-site request forgery (CSRF) protection.
    #: This must be True in production.
    WTF_CSRF_ENABLED = True

    # Services
    # --------

    #: ReCAPTCHA public key.
    RECAPTCHA_PUBLIC_KEY = _env("RECAPTCHA_PUBLIC_KEY")

    #: ReCAPTCHA private key.
    RECAPTCHA_PRIVATE_KEY = _env("RECAPTCHA_PRIVATE_KEY")

    #: Sentry data source name (DSN)
    #: We use Sentry to get notifications about server errors.
    SENTRY_DSN = _env("SENTRY_DSN")

    # We need GOOGLE_APPLICATION_CREDENTIALS for the Google Vision API,
    # but these credentials are fetched by the Google API implicitly,
    # so we don't need to define it on the Config object here.

    # Test-only
    # ---------

    #: If ``True``, enable the Flask debugger.
    DEBUG = False

    #: If ``True``, enable testing mode.
    TESTING = False


class UnitTestConfig(BaseConfig):
    """For unit tests."""

    AMBUDA_ENVIRONMENT = TESTING
    TESTING = True
    SECRET_KEY = "insecure unit test secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = _make_path(Path(__file__).parent / "data" / "file-uploads")

    #: Disable CSRF protection for unit tests, since the Flask test runner
    #: doesn't have good support for it.
    WTF_CSRF_ENABLED = False

    RECAPTCHA_PUBLIC_KEY = "re-public"
    RECAPTCHA_PRIVATE_KEY = "re-private"


class DevelopmentConfig(BaseConfig):
    """For local development."""

    AMBUDA_ENVIRONMENT = DEVELOPMENT
    DEBUG = True


class ProductionConfig(BaseConfig):
    """For production."""

    AMBUDA_ENVIRONMENT = PRODUCTION

    # Deployment credentials
    # ----------------------

    #: Which directory to use on the production machine.
    APP_DIRECTORY = _env("APP_DIRECTORY")
    #: Server username.
    APP_SERVER_USER = _env("APP_SERVER_USER")
    #: Server host.
    APP_SERVER_HOST = _env("APP_SERVER_HOST")


def _validate_config(config: BaseConfig):
    """Examine the given config and fail if the config is malformed.

    :param config: the config to test
    """
    assert config.AMBUDA_ENVIRONMENT in {TESTING, DEVELOPMENT, PRODUCTION}

    if not config.SQLALCHEMY_DATABASE_URI:
        raise ValueError("This config does not define SQLALCHEMY_DATABASE_URI")
    if not config.UPLOAD_FOLDER:
        raise ValueError("This config does not define UPLOAD_FOLDER.")
    if not Path(config.UPLOAD_FOLDER).is_absolute():
        raise ValueError("UPLOAD_FOLDER must be an absolute path.")

    # Production-specific validation.
    if config.AMBUDA_ENVIRONMENT == PRODUCTION:
        # All keys must be set.
        for key in dir(config):
            if key.isupper():
                value = getattr(config, key)
                assert value, key

        # App must not be in debug/test mode.
        assert config.WTF_CSRF_ENABLED
        assert not config.DEBUG
        assert not config.TESTING

        # Google credentials must be set and exist.
        google_creds = _env("GOOGLE_APPLICATION_CREDENTIALS")
        assert google_creds
        assert Path(google_creds).exists()


def load_config_object(name: str):
    """Load and validate an application config."""
    config_map = {
        TESTING: UnitTestConfig,
        DEVELOPMENT: DevelopmentConfig,
        PRODUCTION: ProductionConfig,
    }
    config = config_map[name]
    _validate_config(config)
    return config


def create_config_only_app(config_name: str):
    """Create the application with just its config options set.

    We use this function in Celery to get access to the app context while
    avoiding any other setup work related to the application.
    """
    load_dotenv(".env")
    app = Flask(__name__)
    app.config.from_object(load_config_object(config_name))
    return app
