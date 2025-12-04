Specialized Utilities
=====================

Domain-specific utilities for web, math, concurrency, and more.

webapp
------

Web utilities for Flask and web.py applications: CORS support, XSRF
protection, authentication decorators, URL building, breadcrumb generation,
HTML escaping, JSON encoders with ISO date support.

.. automodule:: libb.webapp
   :members:
   :undoc-members:
   :show-inheritance:

stats
-----

Mathematical and statistical functions: average, variance, standard deviation,
covariance, beta, combinatorics (choose), number parsing, threshold operations.

.. automodule:: libb.stats
   :members:
   :undoc-members:
   :show-inheritance:

sync
----

Synchronization primitives: timeout decorator and context manager
for thread/async operations with configurable timeout handling.

.. automodule:: libb.sync
   :members:
   :undoc-members:
   :show-inheritance:

crypto
------

Cryptography and encoding utilities: base64 file encoding, hashing.

.. automodule:: libb.crypto
   :members:
   :undoc-members:
   :show-inheritance:

geo
---

Geographic utilities: Mercator projection coordinate transformations
(merc_x, merc_y) for mapping applications.

.. automodule:: libb.geo
   :members:
   :undoc-members:
   :show-inheritance:

dir
---

Directory operations: recursive creation, temporary directories,
file searching, safe moving, directory structure inspection, file downloading.

.. automodule:: libb.dir
   :members:
   :undoc-members:
   :show-inheritance:

exception
---------

Exception handling: print exceptions with traceback control,
``try_else`` wrapper for default values on failure.

.. automodule:: libb.exception
   :members:
   :undoc-members:
   :show-inheritance:

future
------

Future pattern implementation for running functions asynchronously
in separate threads with result retrieval.

.. automodule:: libb.future
   :members:
   :undoc-members:
   :show-inheritance:

pandasutils
-----------

Pandas utilities: interval-based operations, multi-column table display,
downcast (memory optimization), fuzzymerge (fuzzy string matching for joins).
Re-exports all pandas functionality.

.. automodule:: libb.pandasutils
   :members:
   :undoc-members:
   :show-inheritance:

rand
----

Random number generation with enhanced seeding, sampling,
and distribution functions.

.. automodule:: libb.rand
   :members:
   :undoc-members:
   :show-inheritance:

thread
------

Threading utilities: ``asyncd`` decorator for async-style syntax,
``threaded`` decorator for background execution in thread pools.

.. automodule:: libb.thread
   :members:
   :undoc-members:
   :show-inheritance:

chart
-----

Plotting utilities for creating charts, particularly time series
visualizations using matplotlib.

.. automodule:: libb.chart
   :members:
   :undoc-members:
   :show-inheritance:

win
---

Windows-specific utilities: command execution, psexec sessions,
file share mounting, WMIC output parsing.

.. automodule:: libb.win
   :members:
   :undoc-members:
   :show-inheritance:
