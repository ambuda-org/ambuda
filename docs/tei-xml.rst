TEI XML
=======


What is TEI XML, and why do we use it?
--------------------------------------

Ambuda's text data is stored as XML, both on disk and in our database.
Specifically, we use a set of XML conventions defined by the *Text Encoding
Initiative* (TEI). For brevity, we use the term *TEI XML* to refer to any XML
that follows the TEI conventions.

TEI XML is the standard format that digital humanities projects now use to
describe and share texts. It's a useful convention, both for receiving texts
from other projects and for publishing texts on our own.

At the same time, the TEI guidelines are complex and overwhelming. They define
hundreds of different elements and attributes that one could use to describe the
structure of essentially any printed book or manuscript.

But, there's a small subset of TEI XML that is suitable for Ambuda's needs.
That's what we will describe here.

.. note::
   These examples use romanized Sanskrit because it renders more cleanly in
   Vim, which I used to type this document. But when you create a TEI document
   for Sanskrit, I recommend using Devanagari.


The document skeleton
---------------------

The `<TEI>` element contains a complete document. Here is its basic structure::

    <TEI xmlns="http://www.tei-c.org/ns/1.0">
      <teiHeader>
        <!-- Metadata: title, author, editor, publication year, etc. -->
      </teiHeader>
      <text>
        <front>
          <!-- Front matter: title pages, dedications, etc. -->
        </front>
        <body>
          <!-- Main text content. -->
        </body>
        <back>
          <!-- Back matter: appendices, mainly. -->
        </back>
      </text>
    </TEI>

`<teiHeader>` contains a lot of boilerplate, so we recommend just copying an
existing `<teiHeader>` from another TEI document and adapting it for your needs.


Sections of a text
------------------

The `<body>` element contains the text's main content. Often, this content is
in multiple sections. An example::

    <body>
      <div n="1">
        <head>
          <!-- Headings and section titles. -->
        </head>

        <!-- Main section content: verses and paragraphs, mainly. -->

        <trailer>
          <!-- Closing statements to mark the end of a section. -->
        </trailer>
      </div>
    </body>

The `<div>` element defines sections of a text: sargas, adhyāyas, and so on.
Use the `n` attribute to give a clear ordering to each `<div>`.


Verses and paragraphs
---------------------

The `<lg>` element defines a verse. Wrap each line of the verse with `<l>`
elements. An example::

    <lg>
      <l>tapaḥsvādhyāyanirataṁ tapasvī vāgvidāṁ varam ।</l>
      <l>nāradaṁ paripraccha vālmīkirmunipuṅgavam ॥ 1 ॥</l>
    </lg>

The `<p>` element defines a paragraph::

    <p>sa bhagavān sr̥ṣṭvedaṁ jagatttasya ca sthitiṁ cikīrṣuḥ</p>


.. note::

    Each verse or paragraph must have an `xml:id` attribute set. We use this
    attribute for cross-referencing and for assigning unique IDs to each part
    of the text.


Elements for plays and dramas
-----------------------------

The `<sp>` element defines a speech section. Within it, `<speaker>` defines the
person speaking::

    <sp>
      <speaker>sūtradhāraḥ</speaker>
      <p>alamativistareṇa |</p>
    </sp>


The `<stage>` element defines stage directions::

    <stage>iti niṣkrāntaḥ</stage>


Useful inline markup
--------------------

To indicate a correction you made to the underlying text, use `<choice>`,
`<sic>`, and `<corr>`::

    <p>
      Use these elements to correct <choice><corr>typos</corr><sic>tpyos</sic></choice>.
    </p>

If this is extremely verbose, just use `<corr>`::

    <p>
      Use these elements to correct <corr>typos</corr>.
    </p>

To preserving highlighting in the original text, use `<hi>`::

    <p>This is <hi rend="bold">bold</hi> text.</p>


For further reading
-------------------

The `official TEI guidelines`_ define the complete TEI spec. There's a lot of
information here, and we need only a fraction of it.

My favorite part of the guidelines, however, is that each element has a page
that defines what it does, what it can contain, and what can contain it. For
example, `here`_ is the documentation for the `<stage>` element. To navigate to
a different element, just replace the word `stage` in the URL.

.. _`official TEI guidelines`: https://tei-c.org/release/doc/tei-p5-doc/en/html/index.html
.. _`here`: https://tei-c.org/release/doc/tei-p5-doc/en/html/ref-choice.html

