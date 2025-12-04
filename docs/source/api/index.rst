API Reference
=============

libb-util provides 35 specialized modules organized into four categories.
All utilities are accessible from the top-level ``libb`` package.

.. important::

   Always import from the top-level package:

   .. code-block:: python

      # Correct
      from libb import Setting, compose, attrdict

      # Incorrect - never import from submodules
      from libb.config import Setting  # Don't do this!

Module Categories
-----------------

:doc:`core`
    Core utilities for configuration, class manipulation, function composition,
    iterators, text processing, and dictionary operations.

:doc:`collections`
    Specialized collection classes including attribute dictionaries, ordered sets,
    and heap queues with custom comparators.

:doc:`io`
    Input/output operations including CSV/JSON handling, stream utilities,
    process management, and signal handling.

:doc:`specialized`
    Domain-specific utilities for web applications, statistics,
    threading, cryptography, geographic calculations, and more.

.. toctree::
   :maxdepth: 2
   :hidden:

   core
   collections
   io
   specialized
