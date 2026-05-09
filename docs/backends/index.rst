.. _backends:

==================
Supported Services
==================

Swiss Army Upload supports a variety of static hosting providers.

.. toctree::

   teahouse
   git-pages
   neocities
   nekoweb

.. list-table::
   :header-rows: 1

   * - Service
     - Address Prefix
     - :ref:`Files Get/Put <cmd-files>`
     - :ref:`Folder Sync <cmd-dirs>`
     - :ref:`HTTP Redirects <redirects>`
     - :ref:`Custom Headers <headers>`
   * - :ref:`backend-teahouse`
     - ``tea://``
     - ✅
     - ✅
     - ✏️
     - ✏️
   * - :ref:`backend-gitpages`
     - ``pages://``
     - ✅
     - ✏️
     - ✏️
     - ✏️
   * - :ref:`Neocities <backend-neocities>`
     - ``neo://``
     - ✏️
     - ✏️
     - ❌
     - ❌
   * - :ref:`Nekoweb <backend-Nekoweb>`
     - ``neko://``
     - ✏️
     - ✏️
     - ❌
     - ❌
