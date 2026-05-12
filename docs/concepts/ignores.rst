===============
Excluding Files
===============

Generally, there's some files you don't want to upload/download when doing syncs.


Default Excludes
================

By default, Swiss Army Upload does not transfer VCS metadata (currently, ``.git`` and ``.gitignore``).


Additional Excludes
===================

You can exclude additional files by passing their name as ``--exclude`` (eg, ``--exclude .gitkeep``). This can be either a file name or a glob pattern (eg, ``*.txt``).


Exclude Nothing
===============

You can include everything by passing ``--exclude-nothing``.
