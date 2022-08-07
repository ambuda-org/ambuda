from celery import Celery

# pyamqp = RabbitMQ message broker
app = Celery("tasks", broker="pyamqp://guest@localhost//")


@app.task
def add(x, y):
    return x + y
