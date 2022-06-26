import os


def _get(key, default=None):
    return os.environ.get(key, default)


class Config:
    SECRET_KEY = _get("SECRET_KEY", "local secret")
    SQLALCHEMY_DATABASE_URI = _get("SQLALCHEMY_DATABASE_URI", "sqlite:///database.db")


class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = _get("SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:")


class DevelopmentConfig(Config):
    pass


class ProductionConfig(Config):
    APP_DIRECTORY = _get("APP_DIRECTORY")
    APP_SERVER_USER = _get("APP_SERVER_USER")
    APP_SERVER_HOST = _get("APP_SERVER_HOST")


config = {
    "testing": TestConfig,
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
