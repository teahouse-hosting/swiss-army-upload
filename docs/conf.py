# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Swiss Army Upload"
copyright = "2026, Teahouse Hosting"
author = "Teahouse Hosting"

primary_domain = None
highlight_language = None

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "logo-simple.svg"
# html_baseurl = ...

html_theme_options = {
    "style_nav_header_background": "#6B2E57ff",
    # TODO: Link sources to codeberg
}


# Intersphinx

intersphinx_mapping = {
    "teahouse": ("https://docs.teahouse.cafe/", None),
}
