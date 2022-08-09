from celery import Celery

# We use Redis for the broker because RabbitMQ can't reliably return backend
# results to multiple processes, which makes it a non-starter for production
# given that we run multiple gunicorn processes. Source:
#
# > RabbitMQ can store results via rpc:// backend. This backend creates
# > separate temporary queue for each client.
#
# Evidently the RabbitMQ broker + Redis backend setup is common, and we should
# look into it eventually, but for now, we can use Redis for both.
app = Celery(
    "ambuda-tasks",
    backend="redis://localhost:6379/0",
    broker="redis://localhost:6379/0",
    include=["ambuda.tasks.projects"],
)
app.conf.update(task_serializer="json")
