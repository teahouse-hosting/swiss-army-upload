================
Using in Actions
================

Swiss Army Upload is its own GitHub/Forgejo Action:

.. tab:: Forgejo

    .. code-block:: yaml

            steps:
              - uses: https://codeberg.org/teahouse/swiss-army-upload.git@trunk
                with:
                  src: ./docs/_output
                  dest: tea://swiss-army-upload.teahouse.cafe/stable/

.. tab:: GitHub

    .. code-block:: yaml

            steps:
              - uses: teahouse-hosting/swiss-army-upload@trunk
                with:
                  src: ./docs/_output
                  dest: tea://swiss-army-upload.teahouse.cafe/stable/

It'll use the OIDC token (GitHub, Forgejo >=v15) to authenticatate with Teahouse.
