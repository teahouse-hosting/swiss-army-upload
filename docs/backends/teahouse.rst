.. _backend-teahouse:

================
Teahouse Hosting
================

`Teahouse Hosting <https://teahouse.cafe/>`_ is a commercial hosting provider, providing global serving on your domain. They are very friendly to large files and high traffic.

:Website: https://teahouse.cafe/
:Documentation: :external+teahouse:doc:`index`
:Address Prefix: ``tea://``
:Redirects: Yes
:Headers: Yes
:Error Pages: Yes


Authentication
==============

At this time, Swiss Army Upload only supports a single Teahouse login---you can log in to ``tea://``, but you can't log in to ``tea://mysite.example`` and ``tea://othersite.example`` with distinct accounts.


Automations
-----------

Teahouse Hosting supports OIDC tokens from public and first-party CI/CD pipelines--if you're publishing automatically from a git repo, you probably don't need to configure secrets. See TODO for more information.

If SAU is run within a supported service, it'll automatically retrieve and use a token to authenticate with Teahouse. These services are supported:

* GitHub Actions
* GitLab CI/CD (TODO)
* Forgejo Actions
* Circle CI (TODO)


Redirects & Headers
===================

.. note::

    Redirects have not yet been implemented in Swiss Army Upload.

Teahouse supports arbitrary redirects with full HTTP options. You can freely redirect ``/mypage`` to ``/over/here.html`` or to ``https://other.mysite.example/``. Similarly, Teahouse supports modifying headers with few restrictions.

However, all paths must be known and resolved at upload time. Wildcards in ``_headers`` are processed by Swiss Army Upload at upload time, and the complete set of headers are pushed up. (Note that ``_headers`` entries must otherwise exist; a path being mentioned in ``_headers`` will not cause SAU to synthesize a file.)

Similarly, Teahouse does not support wildcard redirects. You cannot redirect ``/dir/*`` to ``/other`` or ``/there/*`` unless all paths are enumerated.

Teahouse supports a special header ``Status-Code`` to cause a page to return something other than ``200 OK``. See :external+teahouse:doc:`guides/objects`.

Headers and redirects are applied to ``_404.html`` and other error pages (see below).


Error Pages
===========

Teahouse supports a custom 404 (Not Found) page. See :external+teahouse:ref:`error-pages` in the Teahouse docs for more information.
