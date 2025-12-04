Quick Start
===========

Basic Usage
-----------

Import utilities directly from the top-level ``libb`` package:

.. code-block:: python

    from libb import Setting, compose, attrdict, timeout, fuzzy_search

Configuration Management
------------------------

The ``Setting`` class provides nested dictionary access with dot notation:

.. code-block:: python

    from libb import Setting

    config = Setting()
    config.database.host = 'localhost'
    config.database.port = 5432
    config.database.name = 'mydb'

    # Access with dot notation
    print(config.database.host)  # 'localhost'

    # Lock to prevent modifications
    config.lock()

    # This would raise an error:
    # config.database.host = 'other'  # Locked!

Function Composition
--------------------

Compose multiple functions together:

.. code-block:: python

    from libb import compose

    add_one = lambda x: x + 1
    multiply_two = lambda x: x * 2

    # compose applies functions right-to-left
    add_then_multiply = compose(multiply_two, add_one)
    result = add_then_multiply(5)  # (5 + 1) * 2 = 12

Attribute Dictionaries
----------------------

Dictionary with attribute-style access:

.. code-block:: python

    from libb import attrdict

    d = attrdict(x=10, y=20)
    print(d.x)    # 10
    print(d['y']) # 20
    d.z = 30      # Add new attribute

Other specialized dictionaries:

.. code-block:: python

    from libb import lazydict, emptydict, bidict

    # Lazy evaluation of function values
    lazy = lazydict(expensive=lambda: compute_something())

    # Returns None for missing keys instead of KeyError
    empty = emptydict()
    print(empty.missing)  # None

    # Bidirectional dictionary
    bi = bidict({'a': 1, 'b': 2})
    print(bi.inverse[1])  # 'a'

Timeout Decorator
-----------------

Add timeouts to functions:

.. code-block:: python

    from libb import timeout

    @timeout(5)  # 5 second timeout
    def slow_function():
        import time
        time.sleep(10)  # This will timeout!

    try:
        slow_function()
    except TimeoutError:
        print("Function timed out!")

Iterator Utilities
------------------

Extended iterator operations:

.. code-block:: python

    from libb import chunked, flatten, unique

    # Split into chunks
    list(chunked([1, 2, 3, 4, 5], 2))
    # [[1, 2], [3, 4], [5]]

    # Flatten nested iterables
    list(flatten([[1, 2], [3, [4, 5]]]))
    # [1, 2, 3, 4, 5]

    # Unique elements preserving order
    list(unique([1, 2, 1, 3, 2, 4]))
    # [1, 2, 3, 4]

Text Processing
---------------

Various text utilities:

.. code-block:: python

    from libb import fuzzy_search, truncate, camelcase

    # Fuzzy string matching
    items = [("Apple Inc", "AAPL"), ("Microsoft Corp", "MSFT")]
    results = fuzzy_search("apple", items)

    # Truncate with ellipsis
    truncate("Hello World", 8)  # "Hello..."

    # Convert to camelCase
    camelcase("hello_world")  # "helloWorld"

Threading Utilities
-------------------

Run functions in background threads:

.. code-block:: python

    from libb import threaded, Future

    @threaded
    def background_task(x):
        import time
        time.sleep(1)
        return x * 2

    # Returns immediately, runs in background
    future = background_task(21)

    # Get result when ready
    result = future.result()  # 42
