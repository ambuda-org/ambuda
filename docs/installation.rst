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

All of Ambuda's Python dependencies are declared in `requirements.txt`. The
file is quite messy right now, but the major dependencies are:

- `Flask` for web serving.
- `SQLAlchemy` for querying the database.
- `indic_transliteration` for transliterating Sanskrit text.

You can install them with::

    $ python3 -m venv env
    $ . env/bin/activate
    $ pip install -r requirements.txt

Similarly, all of our JavaScript dependencies are declared in `package.json`.
As of when I wrote this sentence, we use `npm` only for Tailwind::

    $ npm install


Environment Setup
-----------------

It's suggested to keep all relevant environment variables in a `.env` file.
The list of necessary variables are as followed::

    export FLASK_ENV=development
    export GOOGLE_APPLICATION_CREDENTIALS=

Run the following to pull all these environment variables::
    
    $ source .env

This sourcing is included as part of make command when you run the flask
server::

    $ make devserver


Data dependencies
-----------------

Broadly, we use two types of data:

1. Data that we've sanitized and store in our own Git repositories.
2. Data that we fetch directly from third-party sources.

To fetch (1), run these two scripts::

    ./scripts/fetch-dcs-data.sh
    ./scripts/fetch-gretil-data.sh

.. warning::

    You'll need to run the scripts whenever you want to refresh the underlying
    data. In the future, Ambuda will manage all of this for you.

All of the scripts that add data to the database are located under
`ambuda/seed`. For example, you might add the Apte dictionary::

    python -m ambuda.seed.dictionaries.apte

Then you might add some texts from our GRETIL snapshot::

    python -m ambuda.seed.texts.gretil

These two should be enough to play around with Ambuda. But for the full
experience, we recommend running all of the scripts in `ambuda/seed`.

If you see a `KeyError` related to `FLASK_ENV`, make sure to set your environment
variables, as detailed in the previous section.

.. note::

    Ambuda's seed scripts download data from the Internet. Generally, our seed
    scripts cache this data in a `.cache` directory located at the project
    root. This cache makes it easy to iterate on a script that fetches data
    from the Internet.

    So if you're wondering why Ambuda is taking up so much space on disk, check
    the `.cache` directory and delete it if you need to.


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
