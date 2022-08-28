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
    redis-cli ping


.. _tutorial: https://www.digitalocean.com/community/tutorials/how-to-install-and-secure-redis-on-ubuntu-20-04


Celery
------

For setup, see this `guide`_. Copied for reference::

    # Step 0: Define the Celery user and group
    # ----------------------------------------
    # The Celery docs do this, so I have as well.
    # You can skip this step if you want to use another user/group combo.

    # Create the 'celery' user.
    sudo adduser celery

    # Create the 'celery' group.
    sudo groupadd celery

    # Disable shell access for 'celery'.
    sudo usermod -s /sbin/nologin celery

    # Add 'celery' to the 'celery' group.
    sudo usermod -a -G celery celery

    # Step 1: Define the Celery service
    # ---------------------------------

    # You can copy this config almost as-is:
    # https://docs.celeryq.dev/en/stable/userguide/daemonizing.html#service-file-celery-service
    sudo nano /etc/systemd/system/celery.service

    # Register the new service
    sudo systemctl daemon-reload

    # Auto-start Celery if the server restarts.
    sudo systemctl enable celery.service

    # Step 2: Configure the Celery service
    # ------------------------------------

    # You should adapt this config based on your environment:
    # https://docs.celeryq.dev/en/stable/userguide/daemonizing.html#generic-systemd-celery-example
    sudo nano /etc/conf.d/celery

    # Step 3: Run Celery
    # ------------------

    # You might need to change permissions on these directories:
    sudo chown -R $USER:root /var/run/celery
    sudo chown -R $USER:root /var/log/celery

.. _guide: https://docs.celeryq.dev/en/stable/userguide/daemonizing.html
