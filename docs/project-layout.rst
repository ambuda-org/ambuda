Project layout
==============

Many of the toplevel files in the project directory are specific to our
production environment.

- `ambuda` contains the main server code.

- `data` contains third-party data. (Not in version control.)

- `docs` contains this documentation.

- `env` contains our Python dependencies. (Not in version control.)

- `migrations` contains database migration logic. For details on how to run
  migrations, see :doc:`/managing-the-database`.

- `node_modules` contains our JavaScript dependencies. (Not in version control.)

- `production` contains production configs. (Not in version control.)

- `scripts` contains various initialization scripts for the repo.

- `test` contains all of our unit tests.


Core code
---------

`ambuda` contains the main server code, and this is where you will spend most
of your time. Here are the toplevel files in this directory:

- `__init__.py` is the main entrypoint to Ambuda. It creates the app, sets up
  various URL routes, and adds filters that we can use in our template logic.

- `admin.py` defines our internal admin panel, which we use to make ad-hoc
  changes to our production data.

- `auth.py` contains our authentication logic.

- `consts.py` contains important constants.

- `database.py` defines the database schema. This is an important file that you
  should change only with great care.

- `enums.py` contains small enumerated data that we also store in the database.

- `filters.py` contains template filters.

- `queries.py` contains common database queries.

- `xml.py` contains common database queries.

And the important subdirectories:

- `data` contains our third-party data. (Not in version control.)

- `models` defines our SQL table schemas and their relationships. All of these
  models are imported into `database.py`.

- `scripts` contains utility scripts. Mostly, these are cleanup scripts that
  prepare text and parse data for the data repos that Ambuda depends on.

- `seed` contains scripts to add data to the database. 

- `static` contains static assets (CSS and JS, mainly).

- `tasks` contains long-running background tasks. (Comnig soon.)

- `templates` contains HTML templates.

- `utils` contains various small utility functions.

- `views` contains Ambuda's view logic, which combines most of the above to
  create server responses.


Database seed scripts
---------------------

Every database seed script is *idempotent*. That is, running a seed script
hundreds of times has the same effect as running it once. Idempotence is
important because it lets us experiment with seed scripts without corrupting
the database over and over.


Views
-----

(This section expects a basic working knowledge of Flask.)

- `proofing` contains all views related to texts. Everything under the `/texts`
  URL prefix is located here.

- `reader` contains all views related to texts. Everything under the `/texts`
  URL prefix is located here.

- `about.py` contains basic pages about Ambuda: our mission, values, etc.

- `api.py` contains an API blueprint, which decocarates all API routes that
  Ambuda uses.

- `auth.py` contains our authentication endpoints: sign in, sign out, etc.

- `dictionaries.py` contains all views related to dictionary lookups.
  Everything under the `/dictionaries` URL prefix is located here.

- `site.py` contains basic high-level site pages, such as the About and Contact
  pages.
