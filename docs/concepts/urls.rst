==============
Site Addresses
==============

Throughout Swiss Army Upload, sites are referred to by "URLs" or "addresses". Normally this would be something like ``https://yoursite.example/page.html``, but within SAU, they are slightly different.

Addresses in general take the form of ``<service>://<site domain>/<file>`` (eg, this page is ``tea://swiss-army-upload.teahouse.cafe/urls.html``), and can refer to a few different things:

* ``<service>:``: This refers to a service overall, almost always about :ref:`authentication <cmd-login>`.
* ``<service>://<site>``: This refers to either the site overall (again, for :ref:`authentication <cmd-login>`) or the root folder of your site (for :ref:`sync <cmd-sync>`)
* ``<service>://<site>/<path>``: This refers to either a specific file (for :ref:`get and put <cmd-get>`) or a sub-folder (for :ref:`sync <cmd-sync>`)

The specific list of service names can be found in :ref:`backends`.
