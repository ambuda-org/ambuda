Quickstart
==========

All of Ambuda's major commands are in `Makefile`.


Running the development server
------------------------------

After you've cloned the repo, you can bring up a minimal setup by running the
following::

    make install
    make db_seed_basic
    make devserver

Then go to `localhost:5000` to see the local application.

If you also plan to make CSS changes, run the following command in a
separate terminal window::

    make tailwind_watcher

Roughly, Tailwind generates a new CSS file whenever it detects certain changes
to Ambuda's HTML files. For more details, see the `Tailwind docs`_.

.. _Tailwind docs: https://tailwindcss.com/docs/


Linting and testing
-------------------

For linting, you can use::

    # Lints both JS and Python.
    # To lint just Python, run `black .`
    # To lint just JS, run `make eslint`.
    make lint

To run unit tests, you can simply run::

    make test

And to check test coverage, run::

    make coverage


Database migrations
-------------------

Database migrations are complex. If you're pulling an upstream change that
contains a database schema change, run this command to upgrade your local
database:

    alembic upgrade head

See :doc:`managing-the-database` to learn more about how to work with the test
database and safely make schema changes.


Documentation
-------------

Finally, you can generate these docs with::

    make docs

Then you can view the output by opening `_build/index.html`.
