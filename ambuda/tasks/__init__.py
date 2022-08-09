from celery import Celery


# For context on why we use Redis for both the backend and the broker, see the
# `Background tasks with Celery` doc.
app = Celery(
    "ambuda-tasks",
    backend="redis://localhost:6379/0",
    broker="redis://localhost:6379/0",
    include=["ambuda.tasks.projects"],
)
app.conf.update(task_serializer="json")
