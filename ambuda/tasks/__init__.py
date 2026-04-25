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
from dotenv import load_dotenv

# This may be done implicitly elsewhere, but load quickly so we're sure that
# Flask and Celery has the same env.
load_dotenv()

# For context on why we use Redis for both the backend and the broker, see the
# "Background tasks with Celery" doc.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_is_testing = os.getenv("AMBUDA_ENVIRONMENT") == "testing"

app = Celery(
    "ambuda-tasks",
    backend=redis_url,
    broker=redis_url,
    include=[
        "ambuda.tasks.projects",
        "ambuda.tasks.ocr",
        "ambuda.tasks.tagging",
        "ambuda.tasks.text_exports",
        "ambuda.tasks.batch_llm",
        "ambuda.tasks.text_validation",
        "ambuda.tasks.uncovered_reports",
    ],
)
app.conf.update(
    # In the test environment, run tasks in-process so they never touch Redis.
    # The conftest also sets this, but this acts as a safety net.
    task_always_eager=_is_testing,
    task_eager_propagates=_is_testing,
    # Force arguments to be plain data by requiring them to be JSON-compatible.
    task_serializer="json",
    # Set the default task timeout here. Other tasks can override it.
    task_time_limit=600,
)

import ambuda.tasks.signals  # noqa: F401 — register signal handlers
