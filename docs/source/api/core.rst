Core Utilities
==============

The core utilities provide fundamental functionality for configuration,
class manipulation, function composition, and common operations.

config
------

Configuration management with the ``Setting`` class - a nested dictionary
with dot notation access, lock/unlock mechanism, and environment-based
configuration loading.

.. automodule:: libb.config
   :members:
   :undoc-members:
   :show-inheritance:

classes
-------

Class utilities including singleton enforcement, memoization, lazy properties,
metaclass resolution, and dynamic instance extension.

.. automodule:: libb.classes
   :members:
   :undoc-members:
   :show-inheritance:

func
----

Function decorators and composition utilities: compose, decompose, repeat,
delay, suppresswarning, MultiMethod dispatch.

.. automodule:: libb.func
   :members:
   :undoc-members:
   :show-inheritance:

iter
----

Iterator utilities extending itertools: chunking, partitioning, windowing,
flattening, grouping, and sequence operations.

.. automodule:: libb.iter
   :members:
   :undoc-members:
   :show-inheritance:

text
----

Text processing: encoding fixes, camelCase conversion, fuzzy search,
number parsing, truncation, base64 encoding, strtobool.

.. automodule:: libb.text
   :members:
   :undoc-members:
   :show-inheritance:

format
------

String formatting utilities for numbers, currency, time intervals,
phone numbers, capitalization, and custom number formats.

.. automodule:: libb.format
   :members:
   :undoc-members:
   :show-inheritance:

path
----

Path operations: add to sys.path, get module directory, context manager
for directory changes, script name extraction.

.. automodule:: libb.path
   :members:
   :undoc-members:
   :show-inheritance:

dicts
-----

Dictionary utilities: inversion, key/value mapping, flattening, nested access,
multikey sorting, comparison, tree operations.

.. automodule:: libb.dicts
   :members:
   :undoc-members:
   :show-inheritance:

module
------

Module management: dynamic importing, module patching, class instantiation,
virtual modules, package discovery.

.. automodule:: libb.module
   :members:
   :undoc-members:
   :show-inheritance:

typedefs
--------

Type definitions for file-like objects, IO streams, and common data types
used across the library.

.. automodule:: libb.typedefs
   :members:
   :undoc-members:
   :show-inheritance:
