import os


def _get(key, default=None):
    return os.environ.get(key, default)


class Config:
    SECRET_KEY = _get("SECRET_KEY", "local secret")


class DevelopmentConfig(Config):
    pass


class ProductionConfig(Config):
    APP_DIRECTORY = _get("APP_DIRECTORY")
    APP_SERVER_USER = _get("APP_SERVER_USER")
    APP_SERVER_HOST = _get("APP_SERVER_HOST")


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
