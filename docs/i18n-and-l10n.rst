Internationalization and Localization
=====================================

Internationalization and localization, or **i18n and l10n** for short, are how
we prepare a website for multiple regions and languages. We use i18n and l10n
to present Ambuda's interface in multiple languages. As of this document, we
have default support for English and limited support for Sanskrit.

This doc describes our i18n and l10n process so that you can maintain existing
i18n/l10n logic and add a new locale to the site.

Roughly, our process has three steps:

1. First, we annotate all translatable text in the application.
2. Next, we create translation files for each locale we care about.
3. Finally, we expose these locale options to the end user.


Annotating translatable text
----------------------------

We manage i18n and l10n through the `Flask-Babel`_ extension, which we
initialize
when creating our Flask app::

    # ambuda/__init__.py:create_app
    babel = Babel(app)

Once we load this extension, we then annotate all of the text we wish to
translate with the `_` function, which Flask-Babel injects into the `Jinja`_
template context. For example::

    # some-file.html
    {{ _('Texts') }}

.. _`Flask-Babel`: https://python-babel.github.io/flask-babel/
.. _Jinja: https://jinja.palletsprojects.com/en/3.1.x/


Creating translation files
--------------------------

All of our translations are stored in translation files. To create these
translation files, we follow a simple four-step process.

We first create a `.pot` (portable object template) file that extracts all
translatable text in the application. This file is a template for our
locale-specific translation data, and we can regenerate it directly from the
application code::

    make babel-extract

From this `.pot` file, we then create one `.po` (portable object) file for each
locale we care about. These files contain locale-specific translation data, and
we save them in version control::

    # Create a new locale file.
    make babel-init locale=sa

    # Update existing locale files.
    make babel-update

Third, we update the `.po` file with our translations. This is the most
labor-intensive part of the i18n/l10n process.

Finally, we compile the locale-specific `.po` files into `.mo` (machine object)
files, which are optimized for machine usage. These are the files that the
Ambuda application uses::

    make babel-compile


Exposing locale options
-----------------------

Once we have `.mo` files, we can expose locale options in our UI.
