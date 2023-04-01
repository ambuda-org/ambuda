"""Main entrypoint for Ambuda's background task runner.

The code here shares some utilities with our Flask application, but otherwise
it is an entirely different program that operates outside the Flask application
context.

Use utilities from outside this package with care.

For more information, see our "Background tasks with Celery" doc:

https://ambuda.readthedocs.io/en/latest/
"""

import os

from celery import Celery, Task
from flask import Flask

# For context on why we use Redis for both the backend and the broker, see the
# "Background tasks with Celery" doc.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def celery_init_app(app: Flask) -> Celery:
    """Initialize the Celery app against our Flask instance.

    Source: https://flask.palletsprojects.com/en/2.2.x/patterns/celery/
    """

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(
        "ambuda-tasks",
        task_cls=FlaskTask,
        backend=redis_url,
        broker=redis_url,
        include=[
            "ambuda.tasks.projects",
            "ambuda.tasks.ocr",
        ],
    )
    celery_app.set_default()
    celery_app.conf.update(
        # Run all tasks asynchronously by default.
        task_always_eager=False,
        # Force arguments to be plain data by requiring them to be JSON-compatible.
        task_serializer="json",
    )

    app.extensions["celery"] = celery_app
    return celery_app
