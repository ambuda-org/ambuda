from celery import Celery

# amqp = RabbitMQ message broker
app = Celery("tasks", backend="rpc://", broker="pyamqp://guest@localhost//")
app.conf.task_serializer = "json"


@app.task
def add(x, y):
    return x + y
