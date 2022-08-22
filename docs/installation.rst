Installation
============

This guide will show you how to install Ambuda and its dependencies. By the end
of this guide, you'll have a working devserver that contains the same text and
data as our production server.


Before you begin
----------------

We recommend using the latest version of Python. At a mininum, Ambuda requires
Python 3.9.

We also recommend having a recent version of `npm`. We use `npm` to fetch our
Tailwind watcher, which generates CSS based on changes to our HTML files. (We
currently use npm version 8.5.2.)

We tested this setup on a MacBook running macOS 12.3 Monterey, but we think it
will work on most Unix machines. If you have installation problems that seem
specific to the Ambuda project, please file an issue on our repo or let us know
on our Discord server.


Code dependencies
-----------------

Start by downloading Ambuda's project code from GitHub::

    $ git clone git@github.com:ambuda-org/ambuda.git

You can install all dependencies with a simple `make` call::

    $ make install

If the install command succeeds, you can bring up a basic version of Ambuda by
running the following commands::

    # Enter the virtual environment.
    # (If you're using a non-Bash shell, you might need to use a different
    # command. Search "virtualenv $YOUR_SHELL_HERE" for details.
    $ source env/bin/activate

    # Then, start the development server.
    $ make devserver


Environment setup
-----------------

Behind the scenes, we configure Ambuda by setting various environment
variables, which is the standard practice for Flask applications. To organize
all of these settings, we keep environment variables in a `.env` file in the
project root.

`make install` creates an `.env` file for you. If you ever need to add more
variables in the future, just edit `.env`. All Ambuda code will refer to
`.env` by default.

If you need access to these environment variables as part of some other script,
you can run the following command for shell scripts::
    
    $ source .env

Or the following commands for Python scripts:

.. code-block:: python

    from dotenv import load_dotenv
    load_dotenv(".env")


Docker setup (beta)
-----------------

This feature is still under development and may change. You can alternatively
run a local development environment using Docker by running:

    make start-docker


Data dependencies
-----------------

The `ambuda` repo doesn't contain any of the texts, dictionaries, or parse data
that we serve on our library. To install this data, we run different **seed
scripts** that fetch the data we need from the Internet.

Running all of the Ambuda seed scripts can be quite slow. For basic dev tasks,
we recomemnd running just a basic subset of them::

    make db-seed-basic

If you want to install everything and are willing to wait, you can run::

    make db-seed-all

.. note::

    Generally, our seed scripts cache any downloaded data in a cache directory
    at `data/download-cache`. We define this cache so that you can quickly
    rebuild the database if you need to install from scratch.


Service dependencies
--------------------

Ambuda has several important service dependencies. These dependencies are
required only for specific features on Ambuda. For general usage, you can skip
these.


Google's Cloud Vision API
^^^^^^^^^^^^^^^^^^^^^^^^^

We use the Google's Cloud Vision API, which we use to perform optical character
recognition (OCR) on scanned books.

You should set up the Cloud Vision API if you want to run OCR locally. To do
so, refer to the documentation here:

- `How to add application credentials for Google Cloud`_
- `How to enable the Vision API`_

.. _`How to add application credentials for Google Cloud`: https://cloud.google.com/docs/authentication/getting-started#auth-cloud-implicit-python
.. _`How to enable the Vision API`: https://cloud.google.com/vision/docs/before-you-begin


reCAPTCHA
^^^^^^^^^

We use reCAPTCHA as an anti-spam measure when users create an account.

You should set up reCAPTCHA credentials if you want to test the authentication
flow locally. To do so, refer to the documentation here:

- `How to set up reCAPTCHA`_

Then, download your JSON credentials and set the `GOOGLE_APPLICATION_CREDENTIALS`
environment variable in your `.env` file to point to these credentials.

.. note::
    Ambuda uses reCAPTCHA v2. It is slightly less sophisticated than v3 but has
    better privacy guarantees.

.. _`How to set up reCAPTCHA`: https://developers.google.com/recaptcha/intro


Sentry
^^^^^^

We use Sentry to log server errors when we run in production.

You should set up Sentry only if you want to emulate our production logging
setup. To do so, refer to the documentation here:

- `How to set up Sentry`_

.. _`How to set up Sentry`: https://docs.sentry.io/platforms/python/
