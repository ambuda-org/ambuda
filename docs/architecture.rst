Architecture
============

.. note::
   If you just want to get started, see the :doc:`/quickstart` guide.


Data formats
------------

All of our input data is stored in plain text.

We store text data as XML that conforms to the `TEI`_ standard. TEI is an
enormously complicated spec, and by :doc:`principle (2)<values-and-principles>`,
we would normally reject it. But TEI is a consensus format for encoding
various useful properties of a text, such as:

- metadata, including a text's source, author, publisher, and so on.
- structure, including chapters, sections, headers, and footers.
- unique IDs for specific objects of interest, such as verses and paragraphs.
- corrections to the original text, as needed.

The full TEI spec has hundreds of elements, but we restrict ourselves to a
small subset.

.. _TEI: https://tei-c.org

Dictionary data, which mostly comes from the Cologne Digital Sanskrit Lexicons
project, is typically in XML.

Parse data uses a custom format that is similar to a TSV, and parsing logic is
in `ambuda.seed.dcs`. (Our raw upstream parse data uses the CoNLL-U format, but
this is too verbose for our needs and makes it difficult to quickly correct
parse errors in the data.)


Data storage
------------

We store our data in a `SQLite`_ database.

SQLite is fast and great for prototyping. Ambuda is a read-heavy website, so
SQLite also scales well with increased traffic. Even if we become more
write-heavy in the future, SQLite's write-ahead logging (WAL) is an option for
higher write throughput. And if all of that fails, there's a clear migration
path to Postgres with excellent tooling to support the migration.

Much of our content is unstructured, but it has basic structured elements -- a
parent text, an XML ID, a correspondence with some other resource -- that fit
well in a traditional database schema. And, both SQLite and Postgres support
JSON columns if we ever need that extra flexibility.

.. _SQLite: sqlite.org


Server
------

Our webserver is implemented in Python and runs on WSGI (Gunicorn).

Python is not the world's most performant language, but it's great for rapid
prototyping and has strong tooling support. Python 3 type annotations keep the
code manageable, and Python's rich ecosystem of Sanskrit packages makes it a
natural choice. It's a nice bonus as well that Python is extremely popular,
which means that most contributors have some context on it.

Specifically, our backend code is written in `Flask`_, an elegant Python
microframework. We chose Flask because it has a minimal surface area that new
Python developers can easily understand. We use `SQLAlchemy`_, a best-in-class
SQL library, to communicate with our database.

.. _Flask: https://flask.palletsprojects.com/en/2.1.x/
.. _SQLAlchemy: https://www.sqlalchemy.org/


CSS
---

We manage our CSS using `Tailwind`_.

If you're used to more traditional CSS framework, Tailwind might look hideous
at first. But it keeps Ambuda's CSS consistent, predictable, and fairly
professional without needing a complex build step or careful class management.


.. _Tailwind: https://tailwindcss.com


JavaScript
----------

Our frontend code uses vanilla JavaScript with no extra frameworks.

Although we don't use `HTMX`_, we do as much work as we can server-side and use
JavaScript only for small UX features that aren't worth a round-trip on the
network. Some of the philosophy for this can be explained here:

https://htmx.org/essays/a-response-to-rich-harris/

.. _HTMX: https://htmx.org/
