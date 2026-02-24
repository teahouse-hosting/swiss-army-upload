.. _redirects:

=========
Redirects
=========

Background
==========

HTTP is the technical method that your browser uses to talk to servers and get web pages.

One of the features of HTTP is the concept of "redirects": the server telling your browser "actually, the page you want is over there".


Redirects in SAU
================

Swiss Army Upload supports reading a ``_redirects`` file (similar to `Codeberg <https://docs.codeberg.org/codeberg-pages/redirects/>`_ and `Netlify <https://docs.netlify.com/manage/routing/redirects/overview/#syntax-for-the-_redirects-file>`_) and applying them to your site.

However, different services have different capabilities. For example, :ref:`backend-teahouse` does not support wildcards. See :ref:`backends` for specifics.

This is an option on both :ref:`cmd-get` and :ref:`cmd-sync`.
