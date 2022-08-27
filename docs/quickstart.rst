Quickstart
==========

All of Ambuda's major commands are in `Makefile`.


Fresh setup
-----------

After you've cloned the repo, you can bring up a minimal setup by running the
following command::

    make install

.. collapse:: Debug info

    In case this fails with an error (due some change in the database structure) and you already have a local `database.db` - try deleting it. Also see "Database migrations" below.

Next, run the following commands to create a new admin user::

    ./cli.py create-user
    ./cli.py add-role <username> admin


Some parts of Ambuda, such as PDF parsing, need to run tasks in the background.
To add support for these in your local setup, run the following::

    ./scripts/install_osx_dependencies.sh
    make celery

Roughly, Tailwind generates a new CSS file whenever it detects certain changes
to Ambuda's HTML files. For more details, see the `Tailwind docs`_.

.. _Tailwind docs: https://tailwindcss.com/docs/

Updating the local setup
------------------------
If you don't want to run a fresh setup after pulling upstream changes, you can do the following::

    bash
    source env/bin/activate
    pip install -r requirements.txt


Also see "Database migrations" section below.


Running the development server
------------------------------
Run::

    make devserver


Then go to `localhost:5000` to see the local application.

Linting and testing
-------------------

For linting, you can use::

    # Lints both JS and Python.
    # - To lint just Python, run `black .`
    # - To lint just JS, run `make js-lint`.
    make lint

To run unit tests, you can simply run::

    make test

And to check test coverage, run::

    make coverage


Database migrations
-------------------

Database migrations are complex. If you're pulling an upstream change that
contains a database schema change, run this command to upgrade your local
database::

    alembic upgrade head

See :doc:`managing-the-database` to learn more about how to work with the test
database and safely make schema changes.


Documentation
-------------

Finally, you can generate these docs with::

    make docs

Then you can view the output by opening `_build/index.html`.
