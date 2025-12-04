Installation
============

Requirements
------------

- Python 3.9 or higher
- Poetry (recommended) or pip

Basic Installation
------------------

Using Poetry (recommended)::

    git clone https://github.com/bissli/libb-util.git
    cd libb-util
    poetry install

Using pip::

    pip install -e .

Optional Extras
---------------

Install with specific functionality:

.. code-block:: bash

    # Testing dependencies
    poetry install -E test

    # Pandas utilities
    poetry install -E pandas

    # Text processing (chardet, ftfy, rapidfuzz)
    poetry install -E text

    # Web utilities (Flask, web.py, Twisted)
    poetry install -E web

    # Mathematical/plotting (matplotlib)
    poetry install -E math

    # Documentation building
    poetry install -E docs

    # All extras
    poetry install --all-extras

With pip:

.. code-block:: bash

    pip install -e ".[test,pandas,text,web,math]"

Environment Variables
---------------------

The ``config`` module supports the following environment variables:

**Directory Settings**::

    CONFIG_TMPDIR_DIR   # Temporary directory path (used by get_tempdir)
    CONFIG_VENDOR_DIR   # Vendor directory path (used by get_vendordir)
    CONFIG_OUTPUT_DIR   # Output directory path (used by get_outputdir)

If not set, these fall back to the system temporary directory. The local
data directory (via ``get_localdir``) uses ``platformdirs`` to determine
the appropriate location for the current operating system.
