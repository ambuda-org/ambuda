from celery import Celery

# amqp = RabbitMQ message broker
app = Celery(
    "ambuda-tasks",
    backend="rpc://",
    broker="pyamqp://guest@localhost//",
    include=["ambuda.tasks.pdf"],
)
app.conf.update(task_serializer="json")
