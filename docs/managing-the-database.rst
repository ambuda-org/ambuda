Managing the database
=====================


Databases and version control
-----------------------------

To prevent corrupting our production data, our code and our database need to
have the same understanding of what the data looks like: what our tables are
called, what columns they have, and so on.

But although our code lives in a version-controlled system, our database
doesn't. And since our database contains our precious user data, it's something
we can't afford to corrupt.

The usual fix for this problem is to define database **migrations**. Each
migration defines how we want to modify the database and how to undo those
changes if we decide not to keep them.

In Ambuda, we manage our database schemas with `SQLAlchemy`_, and we manage our
migrations with a companion library called `Alembic`_.

This guide will show you how to use Alembic for common development tasks.

.. _SQLAlchemy: https://docs.sqlalchemy.org/en/latest/
.. _Alembic: https://alembic.sqlalchemy.org/en/latest/


Alembic cheatsheet
------------------

Alembic is analogous to Git. We can see the current migration ID::

	alembic current

See the migration history::

	alembic history 

Move up to a newer migration::

	# Move up one migration
	alembic upgrade +1

	# Move up to specific migration
	alembic upgrade <migration_id>

	# Move to latest migration
	alembic upgrade head

And downgrade to the earliest migration::

	# Move down one migration
	alembic downgrade -1

	# Move down to specific migration
	alembic downgrade <migration_id>

	# Move to earliest migration
	alembic downgrade base

We can also modify the database by creating a new migration::

	alembic revision --autogenerate -m "Add my cool column"

Then applying it::

	alembic upgrade head


Initializing the migration system
---------------------------------

We initialize Alembic as part of `make install`. The specific commands we run
here are:: 

	# Create Alembic's migrations table. This tracks the current migration
	# status.
	alembic ensure_version

	# Set the most recent revision as the current one.
	alembic stamp head


How to apply schema changes
---------------------------

Usually, all you'll need to do is upgrade to the latest migration::

	alembic upgrade head


How to create schema changes
----------------------------

Alembic can create common changes for you. Just run the following command::

	alembic revision --autogenerate -m "Add my cool column"

Sometimes, custom changes are needed on top. For details and pointers, ask on
the `#backend` channel on our Discord server.


Fixing a broken database
------------------------

In development, it's often just easiest to delete the database and recreate it
from scratch.

Before we merge in a migration, we must verify that we can successfully upgrade
to it and downgrade from it.


For more information
--------------------

See the `Alembic tutorial`_.

.. _Alembic tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
