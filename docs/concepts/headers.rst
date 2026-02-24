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

Swiss Army Upload supports reading a ``_headers`` file (similar to `Netlify <https://docs.netlify.com/manage/routing/headers/>`_) and applying it to your site.

However, different services have different capabilities. For example, :ref:`backend-gitpages` only allows a specific set of headers to be customized. See :ref:`backends` for specifics.

This is an option on both :ref:`cmd-get` and :ref:`cmd-sync`.
