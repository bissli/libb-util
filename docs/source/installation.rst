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

The ``config`` module supports various environment variables for configuration:

**Configuration Files**::

    CONFIG_PROD    # Production config file path
    CONFIG_DEV     # Development config file path
    CONFIG_QA      # QA config file path
    CONFIG_UAT     # UAT config file path

**Application Type**::

    CONFIG_WEBAPP     # Web application mode
    CONFIG_CHECKTTY   # Check TTY mode

**Mail Settings**::

    CONFIG_MAIL_DOMAIN
    CONFIG_MAIL_SERVER
    CONFIG_MAIL_FROMEMAIL
    CONFIG_MAIL_TOEMAIL
    CONFIG_MAIL_ADMINEMAIL
    CONFIG_MANDRILL_APIKEY

**Logging**::

    CONFIG_SYSLOG_HOST
    CONFIG_SYSLOG_PORT
    CONFIG_LOG_MODULES_EXTRA
    CONFIG_LOG_MODULES_IGNORE

**Other**::

    CONFIG_TMPDIR   # Temporary directory path
    CONFIG_GPG_DIR  # GPG directory path
