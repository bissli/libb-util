Collection Classes
==================

Specialized collection classes with enhanced functionality beyond
Python's built-in collections.

attrdict
--------

Six dictionary classes with special behaviors:

- ``attrdict``: Attribute-style access (dot notation)
- ``lazydict``: Lazy evaluation of function values
- ``emptydict``: Returns None for missing keys
- ``bidict``: Bidirectional dictionary with inverse mapping
- ``MutableDict``: Ordered dict with insert_before/insert_after
- ``CaseInsensitiveDict``: Case-insensitive key access

.. automodule:: libb.attrdict
   :members:
   :undoc-members:
   :show-inheritance:

orderedset
----------

``OrderedSet``: Set that preserves insertion order with unique elements.
Combines the uniqueness guarantee of sets with the ordering of lists.

.. automodule:: libb.orderedset
   :members:
   :undoc-members:
   :show-inheritance:

heap
----

``ComparableHeap``: Heap queue with custom comparator key function.
Useful when you need priority queue behavior with custom ordering.

.. automodule:: libb.heap
   :members:
   :undoc-members:
   :show-inheritance:
