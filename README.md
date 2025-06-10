Bissli Utilities Module
=======================

![libb](https://github.com/bissli/libb/raw/master/bissli.jpg "Bissli - via wikipedia https://en.wikipedia.org/wiki/Bissli")

Contents
--------

## Overview

This repository contains a collection of utility modules designed to enhance
productivity and simplify common programming tasks in Python. Below is a summary
of each module and its primary functionalities.

## Modules

### `io.py`
Provides functions for rendering CSV data, working with zipped CSV files, and
converting iterables to streams.

### `dir.py`
Contains utilities for directory and file manipulation, including functions to
create temporary directories and manage file shares.

### `chart.py`
Facilitates the creation of charts and plots, particularly for time series data.

### `streamutils.py`
Offers tools for working with streams, including asynchronous execution and
threading utilities.

### `win.py`
Windows-specific utilities for running commands, managing sessions, and parsing
WMIC output.

### `dictutils.py`
Functions for working with dictionaries, such as inversion, mapping, and
flattening nested structures.

### `funcutils.py`
Decorators and higher-order functions to compose functions, repeat execution,
and handle exceptions.

### `configutils.py`
Provides a `Setting` class for configuration management and functions to load
configuration options.

### `classutils.py`
Helpers for class operations, such as singleton enforcement, lazy properties,
and dynamic inheritance. [Full documentation](docs/classutils.md)

### `textutils.py`
Text processing functions for fixing encoding issues, fuzzy searching, and
boolean string conversion.

### `setutils.py`
Utilities for working with sets, including ordered sets with unique elements.

### `util.py`
General programming utilities, including timeout management and list
manipulation functions.

### `webutils.py`
Web programming utilities for handling CORS, authentication, and formatting
responses.

### `mathutils.py`
Mathematical utilities for statistical calculations, variance, and covariance.

### `iterutils.py`
Itertools extensions for chunking, partitioning, and creating infinite
iterators.

### `mimetypesutils.py`
MIME type utilities for guessing file extensions and types.

### `moduleutils.py`
Module management utilities for importing and patching modules dynamically.

### `montecarlo.py`
Monte Carlo simulation utilities for financial and mathematical modeling.

### `syncd.py`
Synchronization utilities for managing concurrent operations.

### `thread.py`
Threading utilities to simplify running functions in separate threads.

### `typingutils.py`
Type definitions for file-like objects and other common data types.

### `rand.py`
Random number generation utilities with seeding and sampling functions.

### `exception.py`
Exception handling utilities to print and manage exceptions.

### `pd.py`
Pandas DataFrame utilities for downcasting and merging with fuzzy matching.

### `future.py`
Future pattern implementation for asynchronous execution of functions.

### `procutils.py`
Process utilities for managing system processes and executing shell commands.

## Installation

To install the utilities, clone the repository and install the required
dependencies:

```bash
git clone https://github.com/your-repo/libb.git
cd libb
pip install -r requirements.txt
```

Environemntal Variables
-----------------------
`config.py`
```
CONFIG_PROD (
or CONFIG_DEV
or CONFIG_QA
or CONFIG_UAT
)

Apptype:
- CONFIG_WEBAPP
- CONFIG_CHECKTTY

Enable mail:
- CONFIG_MAIL_DOMAIN
- CONFIG_MAIL_SERVER
- CONFIG_MAIL_FROMEMAIL
- CONFIG_MAIL_TOEMAIL
- CONFIG_MAIL_ADMINEMAIL
- CONFIG_MANDRILL_APIKEY

Enable syslog:
- CONFIG_SYSLOG_HOST
- CONFIG_SYSLOG_PORT

Tempdir:
- CONFIG_TMPDIR

Logging:
- CONFIG_LOG_MODULES_EXTRA
- CONFIG_LOG_MODULES_IGNORE

GPG:
- CONFIG_GPG_DIR
```

## Usage

Import the desired utility module in your Python script and use the provided
functions:

```python
from libb import util

# Use a utility function
result = util.some_utility_function(args)
```

## Contributing

Contributions to this project are welcome. Please follow the contribution
guidelines outlined in `CONTRIBUTING.md`.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file included
in the repository.
