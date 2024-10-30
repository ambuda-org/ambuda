Quickstart
==========

All of Ambuda's major commands are in `Makefile`.


Running the development server
------------------------------

After you've cloned the repo, you can bring up a minimal setup by running the
following command::

    make install

Next, run the following commands to create a new admin user::

    ./cli.py create-user
    ./cli.py add-role --username <username> --role admin

After that, you can bring up the development server::

    make devserver

Then go to `localhost:5000` to see the local application.

Some parts of Ambuda, such as PDF parsing, need to run tasks in the background.
To add support for these in your local setup, run the following::

    ./scripts/install_osx_dependencies.sh
    make celery

To quickly create admin users, use `cli.py`::

    ./cli.py create-user

    # For available roles, see the `SiteRole` enum in `enums.py`.
    ./cli.py add-role --username $my_user --role admin


Linting and testing
-------------------

For linting, you can use::

    make py-lint
    make js-lint

To run unit tests, run::

    make test

To run unit tests, including integration tests with Playwright, run::

    make test_all

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
