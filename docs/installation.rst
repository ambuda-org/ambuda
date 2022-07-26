Installation
============

This guide will show you how to install Ambuda and its dependencies.


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

Start by downloading our project code from GitHub::

    $ git clone git@github.com:ambuda-project/ambuda.git

You can install all dependencies with a simple `make` call::

    $ make install


Environment setup
-----------------

We configure Ambuda by setting various environment variables, which is the
standard practice for Flask applications. To organize all of these settings, we
keep environment variables in a `.env` file in the project root.

`make install` creates an `.env` file for you. If you ever need to add more
variables in the future, just edit that file. All Ambuda code will refer to
that file by default.

If you need access to these environment variables as part of some other script,
you can run::
    
    $ source .env


Data dependencies
-----------------

Ambuda is more interesting when it can serve useful data. To start, you might
install our current texts::

    python -m ambuda.seed.texts.ramayana
    python -m ambuda.seed.texts.mahabharata
    python -m ambuda.seed.texts.gretil

Then you might add parse data::

    python -m ambuda.seed.dcs

And a few dictionaries::

    python -m ambuda.seed.dictionaries.apte
    python -m ambuda.seed.dictionaries.mw

For the full experience, we recommend running all of the scripts in `ambuda/seed`.

.. note::

    Ambuda's seed scripts download data from the Internet. Generally, our seed
    scripts cache this data in a cache directory at `data/download-cache` in
    case you need to re-run them.


Service dependencies
--------------------

.. note::
    These dependencies are required only for specific features on Ambuda. For
    general usage, you can skip these.

We have two service dependencies:

- the Cloud Vision API from Google, which we use for OCR.
- reCAPTCHA, which we use as an anti-spam measure. 

You should set up the Cloud Vision API if you want to run OCR locally. To do
so, refer to the documentation here:

- `How to add application credentials for Google Cloud`_
- `How to enable the Vision API`_

.. _`How to add application credentials for Google Cloud`: https://cloud.google.com/docs/authentication/getting-started#auth-cloud-implicit-python
.. _`How to enable the Vision API`: https://cloud.google.com/vision/docs/before-you-begin

Then, download your JSON credentials and set `GOOGLE_APPLICATION_CREDENTIALS`
environment variable to point to these credentials (in your .env file).

You should set up reCAPTCHA credentials if you want to test the authentication
flow locally. To do so, refer to the document here:

- `How to set up reCAPTCHA`_

.. note::
    Ambuda uses reCAPTCHA v2. It is slightly less sophisticated than v3 but has
    better privacy guarantees.

.. _`How to set up reCAPTCHA`: https://developers.google.com/recaptcha/intro
