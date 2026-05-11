===============
Running Locally
===============


Login
=====

After installation, you have to log in to your host with Swiss Army Upload with the ``login`` command. Specifics vary, but it'll be something like::

    $ swiss-army-upload login tea://
    Teahouse email:
    Teahouse password:


Uploading
=========

To upload your website, use the ``sync`` command::

    $ swiss-army-upload sync ./build tea://my.site.example/
