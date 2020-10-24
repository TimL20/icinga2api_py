# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, '/home/tim/Dokumente/Versuche/Python/icinga2api_py/icinga2api_py')


# -- Project information -----------------------------------------------------

project = 'icinga2api_py'
copyright = '2020, Tim Lehner'
author = 'Tim Lehner'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    # 'sphinx.ext.viewcode',  # Adds link to highlighted source code
    'sphinx.ext.todo',
]

# Add any paths that contain templates here, relative to this directory.
# templates_path = ['_templates']

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = 'en'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'
html_theme_options = {
    "description": "Simple Icinga2 API access",
    "page_width": "auto",
    "github_user": "TimL20",
    "github_repo": "icinga2api_py",
    "github_button": True,
    # By default, the sidebar width is too small for "icinga2api_py" without linebreak
    "sidebar_width": "280px",  # Default is 220px
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']


# -- Extension configuration -------------------------------------------------

# -- Options for todo extension ----------------------------------------------

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = True

# Include __init__ docstrings
autoclass_content = 'both'

autodoc_default_options = {
    # Order attributes by occurance in source code
    "member-order": "bysource",
    # Include some special methods
    "special-members": "__call__, __getattr__, __setattr__, __getitem__"
}
