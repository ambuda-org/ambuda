Quickstart
==========

All of Ambuda's major commands are in `Makefile`.


Running the development server
------------------------------

After you've followed the :doc:`/installation` guide, you can bring up the
Ambuda server with::

    make devserver

Then go to `localhost:5000` to see the local application.

If you also plan to make CSS changes, run the following command in a
separate terminal window::

    make tailwind_watcher

Roughly, Tailwind generates a new CSS file whenever it detects certain changes
to Ambuda's HTML files. For more details, see the Tailwind docs.


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

Migrations are in the `migrations/` directory.

Check the current migration setup and status::

    alembic current

Autogenerate a revision::

    alembic revision --autogenerate -m "Add my cool column"

Upgrade to the latest revision::

    alembic upgrade head

For more information, see the `Alembic tutorial`_.

.. _Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html


Documentation
-------------

Finally, you can generate these docs with::

    cd docs/
    make html

Then you can view the output by opening `_build/index.html`.
