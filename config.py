import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


load_dotenv()


def _make_path(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def _env(key: str, default=None) -> str:
    """Fetch a value from the local environment.

    :param key: the envvar to fetch
    """
    return os.environ.get(key, default)


class UnitTestConfig:
    """For unit tests."""

    TESTING = True
    SECRET_KEY = "insecure unit test secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    UPLOAD_FOLDER = _make_path(Path(__file__).parent / "data" / "file-uploads")

    RECAPTCHA_PUBLIC_KEY = "re-public"
    RECAPTCHA_PRIVATE_KEY = "re-private"


class DevelopmentConfig:
    """For local development."""

    DEBUG = True
    SECRET_KEY = "insecure local secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"

    UPLOAD_FOLDER = _env("FLASK_UPLOAD_FOLDER")

    RECAPTCHA_PUBLIC_KEY = _env("RECAPTCHA_PUBLIC_KEY", "re-public")
    RECAPTCHA_PRIVATE_KEY = _env("RECAPTCHA_PRIVATE_KEY", "re-private")


class ProductionConfig:
    """For production."""

    SECRET_KEY = _env("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _env("SQLALCHEMY_DATABASE_URI")

    #: File upload settings
    UPLOAD_FOLDER = _env("FLASK_UPLOAD_FOLDER")

    #: Which directory to use on the production machine.
    APP_DIRECTORY = _env("APP_DIRECTORY")
    #: Server username.
    APP_SERVER_USER = _env("APP_SERVER_USER")
    #: Server host.
    APP_SERVER_HOST = _env("APP_SERVER_HOST")

    # Recaptcha settings
    RECAPTCHA_PUBLIC_KEY = _env("RECAPTCHA_PUBLIC_KEY")
    RECAPTCHA_PRIVATE_KEY = _env("RECAPTCHA_PRIVATE_KEY")


config = {
    "testing": UnitTestConfig,
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
