# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html
import importlib.metadata

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "trs-file-backup"
copyright = "2026, R. Reiner"
author = "R. Reiner"
release = importlib.metadata.version("trs-file-backup")

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    # https://github.com/executablebooks/sphinx-design
    "sphinx_design",
    # https://myst-parser.readthedocs.io/en/latest/intro.html
    "myst_parser",
    # copy button for code blocks
    "sphinx_copybutton",
    # open external links in a new tab
    "sphinx_new_tab_link",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
    "html_image",
]

source_suffix = [
    ".rst",
    ".md",
]

exclude_patterns = ["build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_book_theme"
html_favicon = "_static/empty_favicon.ico"
html_theme_options = {
    "home_page_in_toc": True,
    "repository_provider": "github",
    "repository_url": "https://github.com/TheRedSwabian/trs-file-backup",
    "repository_branch": "develop",
    "path_to_docs": "docs",
    "use_repository_button": True,
    "use_edit_page_button": False,
    "navigation_with_keys": False,
}
html_last_updated_fmt = ""
html_static_path = ["_static"]
