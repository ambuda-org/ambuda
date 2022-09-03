"""Main entrypoint for Ambuda's background task runner.

The code here shares some utilities with our Flask application, but otherwise
it is an entirely different program that operates outside the Flask application
context.

Use utilities from outside this package with care.

For more information, see our "Background tasks with Celery" doc:

https://ambuda.readthedocs.io/en/latest/
"""

import os

from celery import Celery

# For context on why we use Redis for both the backend and the broker, see the
# "Background tasks with Celery" doc.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery(
    "ambuda-tasks",
    backend=redis_url,
    broker=redis_url,
    include=[
        "ambuda.tasks.projects",
        "ambuda.tasks.ocr",
    ],
)
app.conf.update(
    # Run all tasks asynchronously by default.
    task_always_eager=False,
    # Force arguments to be plain data by requiring them to be JSON-compatible.
    task_serializer="json",
)
