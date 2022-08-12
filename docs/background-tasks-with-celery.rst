Background tasks with Celery
============================

Sometimes, a user on Ambuda will request an operation that takes a long time
for our application code to process. Some examples of long-running tasks include:

- calling a third-party API like Google OCR.
- splitting a large PDF into separate images.
- sending an email through a third-party mail server.
- running a regular batch job to convert published texts into PDFs.

To handle these kinds of background tasks, we use `Celery`_, a Python task
scheduler that runs in a separate process from our main application code.

.. _Celery: https://docs.celeryq.dev/en/stable/


Quickstart
----------

First, install Redis, which we use to communicate with the Celery process::

    # Sorry, OSX only for now.
    # If you're on a Linux system, send us a PR!
    ./scripts/install_osx_dependencies.sh

Then, run Celery in a new terminal window::

    make celery


Basic mechanics of Celery
-------------------------

The basic mechanics of Celery are as follows:

1. On our server, we have two processes: our web application code and a Celery
   process that manages a set of worker processes.

2. When we need to create a long-running request, our application sends a
   non-blocking request to Celery. We send this message through a *message
   broker* uch as Redis.

3. Celery receives the request and assigns it to one of its workers.

4. The worker can optionally send status updates to a *backend* component such
   as Redis.

5. Our application can make asynchronous requests to Celery to check on the
   task status. For example, one common pattern is to have a JavaScript
   function that pings the server every N seconds for an update.


Our setup
---------

We use Redis for both our broker and our backend.

We use Redis as our backend because RabbitMQ can't reliably return backend
results to multiple processes, which makes it a non-starter for production
given that we run multiple gunicorn processes. Source:

    RabbitMQ can store results via rpc:// backend. This backend creates
    separate temporary queue for each client.

To simplify our setup, we also use Redis for our broker. It's one less thing to
install, and it's reasonable for now given our low task volume.

The RabbitMQ broker + Redis backend setup is common, and we should look into it
later if Redis doesn't scale.


Gotchas
-------

Our Flask development server uses *hot reloading* to rebuild the application
whenever it detects a code change. Celery does not use hot reloading, and it
will not detect any changes you make to the code it uses.

So if you make a change to your Celery code and want it to take effect, you
must kill then restart the Celery process.

.. note::
    It's possible to hack around this problem, and I would love a pull request
    that does so. Check around first for any prior art we can repurpose here.
