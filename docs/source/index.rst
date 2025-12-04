libb-util Documentation
=======================

A comprehensive collection of utility functions and classes designed to enhance
productivity and simplify common programming tasks in Python.

.. note::
   All utilities should be imported from the top-level ``libb`` package:

   .. code-block:: python

      from libb import Setting, compose, attrdict, timeout

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
