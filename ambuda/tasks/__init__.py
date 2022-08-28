from celery import Celery
import os

# For context on why we use Redis for both the backend and the broker, see the
# `Background tasks with Celery` doc.
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
app = Celery(
    "ambuda-tasks",
    backend=redis_url,
    broker=redis_url,
    include=["ambuda.tasks.projects"],
)
app.conf.update(task_serializer="json")
