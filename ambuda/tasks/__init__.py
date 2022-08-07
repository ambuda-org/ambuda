from celery import Celery

# amqp = RabbitMQ message broker
app = Celery(
    "ambuda-tasks",
    backend="redis://localhost:6379/0",
    broker="redis://localhost:6379/0",
    include=["ambuda.tasks.pdf"],
)
app.conf.update(task_serializer="json")
