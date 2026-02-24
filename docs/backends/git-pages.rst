.. _backend-gitpages:

=========
Git Pages
=========

`Git Pages <https://git-pages.org/>`_ is a non-commercial host focusing on providing websites to Git repos. The main provider is `Grebedoc <https://grebedoc.dev/>`_, but the requirements to self-host are minimal.

:Website: https://git-pages.org/
:Grebedoc: https://grebedoc.dev/
:Address Prefix: ``pages://``
:Redirects: Yes
:Headers: Yes*
:Error Pages: No


Authentication
==============

Git Pages doesn't require knowledge of who is hosting a given website. So you do not need to tell Swiss Army Upload "Grebedoc is hosting mysite.example". But you have to log in to each site you're uploading to individually--you cannot log in to ``pages://``.


Redirects
=========

Git Pages natively supports ``_redirect`` files and Swiss Army Upload just uploads it with minimal interpretation


Headers
=======

Git Pages natively supports ``_headers`` files and Swiss Army Upload just uploads it with minimal interpretation.

Note that only a specific list of headers are allowed. See `I want to set up custom headers <https://grebedoc.dev/#headers>`_ on the Grebedoc site for specifics.
