Running in production
=====================

Some quick adhoc notes for running Ambuda in a production environment.


Gunicorn
--------

Coming soon.


nginx
-----

Coming soon.


Redis
-----

We use Redis as a message broker and backend for our Celery task runner. For
setup, see steps 1 and 2 in this `tutorial`_. Copied for reference::

    # Step 1: Install
    # ---------------
    sudo apt update
    sudo apt install redis-server

    # Edit the Redis conf and set `supervised` to `systemd`.
    sudo nano /etc/redis/redis.conf

    # This will auto-start Redis if the server restarts.
    sudo systemctl enable redis-server.service

    # Step 2: Verify
    # --------------
    sudo systemctl status redis

    # Should print "PONG"
    redic-cli ping


.. _tutorial: https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-redis-on-ubuntu-20-04


Celery
------

For setup, see this `tutorial`_.

.. _tutorial: https://docs.celeryq.dev/en/stable/userguide/daemonizing.html
