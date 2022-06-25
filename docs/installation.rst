Installation
============

This guide will show you how to install Ambuda and its dependencies.


Our tech stack
--------------

Ambuda's backend code is written in `Flask`_, a Python microframework. Our
frontend code uses vanilla JavaScript with no extra frameworks. And we manage
our CSS using `Tailwind`_.

.. _Flask: https://flask.palletsprojects.com/en/2.1.x/
.. _Tailwind: https://tailwindcss.com


Before you begin
----------------

We recommend using the latest version of Python. At a mininum, Ambuda requires
Python 3.9.

We also recommend having a recent version of `npm`. We use `npm` to fetch our
Tailwind watcher, which generates CSS based on changes to our HTML files. (We
currently use npm version 8.5.2.)

We tested this setup on a MacBook running macOS 12.3 Monterey, but we think it
will work on most Unix machines. If you have installation problems that seem
specific to the Ambuda project, please let us know on our Discord channel.


Code dependencies
-----------------

All of Ambuda's Python dependencies are declared in `requirements.txt`. The
file is quite messy right now, but the major dependencies are:

- `Flask` for web serving.
- `SQLAlchemy` for querying the database.
- `indic_transliteration` for transliterating Sanskrit text.

You can install them with::

   $ python -m venv env
   $ . env/bin/activate
   $ pip install -r requirements.txt

Similarly, all of our JavaScript dependencies are declared in `package.json`.
As of when I wrote this sentence, we use `npm` only for Tailwind::

   $ npm install


Data dependencies
-----------------

Ambuda is interesting only because of its data. All of the scripts that add
data to the database are located under `ambuda/seed`. For example, you might
add the Apte dictionary::

   python -m ambuda.seed.dictionaries.apte

Then you might add some texts from our GRETIL snapshot::

   python -m ambuda.seed.texts.gretil

These two should be enough to play around with Ambuda. But for the full
experience, we recommend running all of the scripts in `ambuda/seed`.

.. note::

    Ambuda's seed scripts download data from the Internet. Generally, our seed
    scripts cache this data in a `.cache` directory located at the project
    root. This cache makes it easy to iterate on a script that fetches data
    from the Internet.

    So if you're wondering why Ambuda is taking up so much space on disk, check
    the `.cache` directory and delete it if you need to.
