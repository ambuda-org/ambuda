"""Main entrypoint for Ambuda's background task runner.

Our Celery runner and our Flask application run in separate programs. Since
Celery needs access to certain aspects of our Flask app (in particular, to our
flask-sqlalchemy config), we follow a pattern suggested in the Flask
documentation [1].

Use utilities from outside this package with care.

For more information, see our "Background tasks with Celery" doc:

https://ambuda.readthedocs.io/en/latest/

[1]: https://flask.palletsprojects.com/en/2.2.x/patterns/celery/
"""

import os

from celery import Celery, Task
from flask import Flask

# For context on why we use Redis for both the backend and the broker, see the
# "Background tasks with Celery" doc.
#
# TODO: move REDIS_URL into `config.py`.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def celery_init_app(app: Flask) -> Celery:
    """Initialize the Celery app against our Flask instance.

    Source: https://flask.palletsprojects.com/en/2.2.x/patterns/celery/
    """

    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            # Run tasks within the application context so that they have full
            # database access.
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

    # Make this app instance the "default" handler so that we can use the
    # `shared_task` decorator elsewhere. For details, see the Flask+Celery docs.
    celery_app.set_default()
    celery_app.conf.update(
        # Run all tasks asynchronously by default.
        task_always_eager=False,
        # Force arguments to be plain data by requiring them to be JSON-compatible.
        task_serializer="json",
    )

    # Save this instance on `app` so that we have access to it later.
    app.extensions["celery"] = celery_app
    return celery_app
