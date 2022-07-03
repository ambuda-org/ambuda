import os
from typing import Optional


def _env(key: str) -> str:
    """Fetch a value from the local environment.

    :param key: the envvar to fetch
    """
    return os.environ.get(key)


class TestConfig:
    """For unit tests."""

    TESTING = True
    SECRET_KEY = "insecure test secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


class DevelopmentConfig:
    """For local development."""

    DEBUG = True
    SECRET_KEY = "insecure local secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///database.db"


class ProductionConfig:
    """For production."""

    SECRET_KEY = _env("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _env("SQLALCHEMY_DATABASE_URI")

    #: Which directory to use on the production machine.
    APP_DIRECTORY = _env("APP_DIRECTORY")
    #: Server username.
    APP_SERVER_USER = _env("APP_SERVER_USER")
    #: Server host.
    APP_SERVER_HOST = _env("APP_SERVER_HOST")


config = {
    "testing": TestConfig,
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
