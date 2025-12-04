I/O & System Utilities
======================

Input/output operations and system interaction utilities.

iolib
-----

I/O operations: CSV rendering, zipped CSV handling, iterable-to-stream
conversion, JSON byteification, print suppression.

.. automodule:: libb.iolib
   :members:
   :undoc-members:
   :show-inheritance:

stream
------

Stream utilities: YAML/JSON conversion, binary/text handling,
checksum calculation, stream decorators.

.. automodule:: libb.stream
   :members:
   :undoc-members:
   :show-inheritance:

proc
----

Process utilities: finding processes by name/port, killing processes,
process management.

.. automodule:: libb.proc
   :members:
   :undoc-members:
   :show-inheritance:

signals
-------

Signal handling: ``DelayedKeyboardInterrupt`` context manager for
deferring Ctrl+C during critical sections, signal translation map.

.. automodule:: libb.signals
   :members:
   :undoc-members:
   :show-inheritance:

mime
----

MIME type utilities for guessing file extensions and content types.

.. automodule:: libb.mime
   :members:
   :undoc-members:
   :show-inheritance:
