"""Sphinx configuration for libb-util documentation."""

import sys
from datetime import datetime
import pathlib

sys.path.insert(0, pathlib.Path('../../src').resolve())

project = 'libb-util'
copyright = f'{datetime.now().year}, bissli'
author = 'bissli'
version = '0.0.1'
release = '0.0.1'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    'sphinx_copybutton',
    'myst_parser',
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__',
    'show-inheritance': True,
}
autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'
autodoc_inherit_docstrings = False

autosummary_generate = True
# Handle case conflicts for Dropbox filesystem (MultiMethod vs multimethod)
autosummary_filename_map = {
    'libb.multimethod': 'libb.multimethod_decorator',
}

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
}

myst_enable_extensions = [
    'colon_fence',
    'deflist',
]
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}

html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'navigation_depth': 4,
    'collapse_navigation': False,
    'sticky_navigation': True,
    'includehidden': True,
    'titles_only': False,
    'display_version': True,
    'logo_only': False,
}

html_static_path = ['_static']
html_css_files = ['custom.css']

suppress_warnings = ['autodoc.import_cycle']

autodoc_mock_imports = [
    'flask',
    'web',
    'twisted',
    'matplotlib',
    'pandas',
    'pyarrow',
    'pandas_downcast',
    'rapidfuzz',
    'chardet',
    'ftfy',
]
