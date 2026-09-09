.. _headers:

=======
Headers
=======

Background
==========

HTTP is the technical method that your browser uses to talk to servers and get web pages.

One of the features of HTTP is metadata called headers. This is additional information delivered to your browser alongside the web page itself. The kinds of information can include:

* Is it an image, text, a PDF, etc
* How long your browser should keep a copy before asking the server again
* Can other websites use it
* Should it be displayed or downloaded
* What human language is it in
* How old is the content
* etc


Headers in SAU
==============

Swiss Army Upload supports reading a ``_headers`` file (in the same format as `Netlify <https://docs.netlify.com/manage/routing/headers/>`_) and applying it to your site. However, unlike most tools, it will read multiple.

Swiss Army Upload does not have a concept of a "project" or "site" or "root". Therefore, it cannot read the ``_headers`` file at the root of your site. Instead, it'll read any it can find in any parent directories and resolve them relatively.

That is, ``project/build/_headers`` can refer to ``index.html``, while ``project/_headers`` referring to ``build/index.html`` would be the same file.

Blocks earlier in the file override blocks later in the file, and ``project/build/_headers`` overrides ``project/_headers``.

.. note::

    Different services have different capabilities. For example, :ref:`backend-gitpages` only allows a specific set of headers to be customized. See :ref:`backends` for specifics.
