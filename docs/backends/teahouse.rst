.. _backend-teahouse:

================
Teahouse Hosting
================

`Teahouse Hosting <https://teahouse.cafe/>`_ is a commercial hosting provider, providing global serving on your domain. They are very friendly to large files and high traffic.

:Website: https://teahouse.cafe/
:Documentation: :external+teahouse:doc:`index`
:Address Prefix: ``tea://``
:Redirects: Yes*
:Headers: Yes*
:Error Pages: Yes


Authentication
==============

At this time, Swiss Army Upload only supports a single Teahouse login--you can log in to ``tea://`` but you can't log in to ``tea://mysite.example``.


Automations
-----------

Teahouse Hosting supports OIDC tokens from public and first-party CI/CD pipelines--if you're publishing automatically from a git repo, you probably don't need to configure secrets. See TODO for more information.

If SAU is run within a supported service, it'll automatically retrieve and use a token to authenticate with Teahouse. These services are supported:

* GitHub Actions (TODO)
* GitLab CI/CD (TODO)
* Forgejo Actions (TODO)
* Circle CI (TODO)
* Cirrus CI (TODO)


Redirects
=========

Teahouse supports arbitrary redirects with full HTTP options. You can freely redirect ``/mypage`` to ``/over/here.html`` or to ``https://other.mysite.example/``.

 However, it does not support wildcards or rewrites; you cannot redirect ``/dir/*`` to ``/there`` or to ``/other/*``. You have to know the exact path you're redirecting.

.. note::

    Teahouse hasn't actually implemented redirects yet


Headers
=======

Teahouse supports arbitrary headers with few restrictions.

However, like redirects, wildcards are not supported on the server. If you use a ``_headers`` file, Swiss Army Upload will resolve wildcards to specific paths at upload time.


Error Pages
===========

Teahouse supports a custom 404 (Not Found) page. See :external+teahouse:ref:`error-pages` in the Teahouse docs for more information.
