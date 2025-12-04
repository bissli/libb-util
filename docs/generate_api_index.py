#!/usr/bin/env python3
"""Generate Sphinx index.rst from module exports.

This script auto-populates the Function Reference section of index.rst
using exports from each module's __all__, organized by category.
"""
import sys
from pathlib import Path

# Add src to path for importing libb
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))

from libb._docs import CATEGORY_ORDER, CATEGORY_SECTIONS


def get_module_exports(module_name: str) -> list[str]:
    """Get __all__ exports from a libb submodule."""
    try:
        module = __import__(f'libb.{module_name}', fromlist=[module_name])
        return list(getattr(module, '__all__', []))
    except ImportError as e:
        print(f"Warning: Could not import libb.{module_name}: {e}")
        return []


def generate_autosummary_block(items: list[str]) -> str:
    """Generate an autosummary directive block."""
    if not items:
        return ""
    lines = [
        ".. autosummary::",
        "   :nosignatures:",
        "   :toctree: generated",
        "",
    ]
    for item in items:
        lines.append(f"   libb.{item}")
    return "\n".join(lines)


def generate_section(title: str, description: str, module_names: list[str]) -> str:
    """Generate a section with title and autosummary block."""
    exports = []
    for mod_name in module_names:
        exports.extend(get_module_exports(mod_name))

    if not exports:
        return ""

    lines = [
        f"**{title}** - {description}",
        "",
        generate_autosummary_block(exports),
        "",
    ]
    return "\n".join(lines)


def generate_category(category: str) -> str:
    """Generate all sections for a category."""
    sections = CATEGORY_SECTIONS.get(category, [])
    parts = []
    for title, description, module_names in sections:
        section = generate_section(title, description, module_names)
        if section:
            parts.append(section)
    return "\n".join(parts)


HEADER = """\
libb-util Documentation
=======================

A comprehensive collection of utility functions and classes designed to enhance
productivity and simplify common programming tasks in Python.

.. note::
   All utilities should be imported from the top-level ``libb`` package:

   .. code-block:: python

      from libb import Setting, compose, attrdict, timeout

Function Reference
------------------

"""

CORE_HEADER = """\
Core Utilities
~~~~~~~~~~~~~~

"""

COLLECTIONS_HEADER = """\
Collections
~~~~~~~~~~~

"""

IO_HEADER = """\
Input/Output
~~~~~~~~~~~~

"""

SPECIALIZED_HEADER = """\
Specialized
~~~~~~~~~~~

"""

FOOTER = """\
----

Design Philosophy
-----------------

- **Transparent API**: Always import from top-level ``libb``, never from submodules
- **Graceful Dependencies**: Optional dependencies wrapped for clean imports
- **Short, Singular Names**: Modules use concise names (e.g., ``func`` not ``funcutils``)
- **Comprehensive Exports**: All modules explicitly define their public API via ``__all__``

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   installation
   quickstart

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/index
   api/core
   api/collections
   api/io
   api/specialized

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
"""

CATEGORY_HEADERS = {
    'Core': CORE_HEADER,
    'Collections': COLLECTIONS_HEADER,
    'I/O': IO_HEADER,
    'Specialized': SPECIALIZED_HEADER,
}


def generate_index() -> str:
    """Generate the complete index.rst content."""
    parts = [HEADER]

    for category in CATEGORY_ORDER:
        header = CATEGORY_HEADERS.get(category, f"{category}\n{'~' * len(category)}\n\n")
        content = generate_category(category)
        if content:
            parts.append(header)
            parts.append(content)

    parts.append(FOOTER)
    return "".join(parts)


def main():
    index_path = Path(__file__).parent / 'source' / 'index.rst'
    content = generate_index()
    index_path.write_text(content)
    print(f"Generated {index_path}")


if __name__ == '__main__':
    main()
