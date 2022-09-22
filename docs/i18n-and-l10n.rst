Internationalization and Localization
=====================================

.. note::
    This doc is for software engineers who want to add new translation files to
    the Ambuda application. If you want to help translate but aren't interested
    in the technical details, join our translation effort here:

    https://www.transifex.com/ambuda/ambuda


Internationalization and localization, or **i18n and l10n** for short, are how
we prepare a website for multiple regions and languages. We use i18n and l10n
to present Ambuda's interface in multiple languages. 

This doc describes our i18n and l10n process so that you can maintain existing
i18n/l10n logic and add a new locale to the site.

Roughly, our process has five steps:

1. Annotate all translatable text in the app.
2. Create translation files for each locale we care about.
3. Translate text from English to the locale of interest. 
4. Add these translations to the app.
5. Update the app UI.


1. Annotate translatable text
-----------------------------

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

If a translation varies based on some number, you can use `ngettext`::

    # texts.html
    {{ ngettext('%(num)d page', '%(num)d pages', count) }}

If a translation depends on some specific context, you can use `pgettext`
instead::

    # texts.html
    {{ pgettext('texts', 'About') }}

    # project.html
    {{ pgettext('projects', 'About') }}

    # user.html
    {{ pgettext('users', 'About') }}


.. _`Flask-Babel`: https://python-babel.github.io/flask-babel/
.. _Jinja: https://jinja.palletsprojects.com/en/3.1.x/


2. Create translation files
---------------------------

All of our translations are stored in `.po` (portable object) files, a simple
plain-text file format that is the standard for translation files.

To create these `.po` files, we first create a `.pot` (portable object
template) file that extracts all translatable text in the application. This
file is a template for our locale-specific translation data, and we can
regenerate it directly from the application code at any time::

    # Generates a `.pot` file.
    make babel-extract

From this `.pot` file, we then create one `.po` file for each locale we care
about. These files contain locale-specific translation data, and we can save
them in version control::

    # Create a new locale file from `messages.pot`.
    make babel-init locale=sa

    # Update existing locale files.
    make babel-update


3. Translate text
-----------------

We do our translation work through `Transifex`_, a user-friendly UI for
managing translation projects. You can find our translation project `here`_.

.. _`Transifex`: https://www.transifex.com/
.. _`here`: https://www.transifex.com/ambuda/ambuda


On Transifex, you can upload a `.pot` file as a template for the entire
project, and you can also upload `.po` files per locale.


4. Add translations to the app
------------------------------

Finally, we download the `.po` files created by Transifex and add them to the
`ambuda` repo. All of our translation files should be named with this
convention::

    ambuda/translations/<locale>/LC_MESSAGES/messages.po

where `<locale>` is a short locale code like `sa`.

The Ambuda application cannot use these files directly. Instead, we must first
compile these `.po` files into `.mo` (machine object) files, which are
optimized for machine usage. You can do so with::

    make babel-compile


5. Update the app UI
--------------------

Finally, we update the app UI so that our new locale is available to the end
user.

As of 10 September 2022, our UI is a simple list of links in the Ambuda footer.
Just update the footer and verify that everything works on your dev server.
