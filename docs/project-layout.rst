Project layout
==============

Many of the toplevel files in the project directory are specific to our
production environment. You can ignore almost all of them.


Core code
---------

`ambuda` contains the main server code, and this is where you will spend most
of your time.

Here are the important toplevel files in this directory:

- `__init__.py` is the main entrypoint to Ambuda. It creates the app, sets up
  various URL routes, and adds filters that we can use in our template logic.

- `database.py` defines the database schema. This is an important file that you
  should change only with great care.

- `filters.py` contains template filters.

- `queries.py` contains common database queries.

And here are the important submodules:

- `scripts` contains utility scripts. Mostly, these are cleanup scripts that
  prepare text and parse data for the data repos that Ambuda depends on.

- `seed` contains scripts to add data to the database. 

- `static` contains static assets (CSS and JS, mainly).

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

- `api.py` contains an API blueprint, which decocarates all API routes that
  Ambuda uses.

- `cheda.py` (name might change) contains all views related to parse data.

- `dictionaries.py` contains all views related to dictionary lookups.
  Everything under the `/dictionaries` URL prefix is located here.

- `site.py` contains basic high-level site pages, such as the About and Contact
  pages.

- `texts.py` contains all views related to texts. Everything under the `/texts`
  URL prefix is located here.
