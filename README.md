Bissli Utilities Module
=======================

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://bissli.github.io/libb-util/)

![libb](https://raw.githubusercontent.com/bissli/libb-util/refs/heads/master/bissli.jpg "Bissli - via wikipedia https://en.wikipedia.org/wiki/Bissli")

Contents
--------

## Overview

A comprehensive collection of utility functions and classes designed to enhance productivity and simplify common programming tasks in Python. The library follows a **transparent API design** where all utilities are imported from the top-level `libb` package, making the internal module organization an implementation detail.

## Design Philosophy

- **Transparent API**: Always import from top-level `libb`, never from submodules
- **Graceful Dependencies**: Optional dependencies wrapped in `contextlib.suppress` for clean imports
- **Short, Singular Names**: Modules use concise names (e.g., `func` not `funcutils`)
- **Comprehensive `__all__` Exports**: All modules explicitly define their public API

```python
# ✅ CORRECT: Import from top-level libb
from libb import Setting, compose, downcast, expandabspath

# ❌ WRONG: Never import from submodules
from libb.config import Setting  # Don't do this!
```

## Module Organization

### Core Utilities (10 modules)

#### `config.py`
Configuration management with the `Setting` class - a nested dictionary with dot notation access, lock/unlock mechanism, and environment-based configuration loading.

#### `classes.py`
Class utilities including singleton enforcement, memoization, lazy properties, metaclass resolution, and dynamic instance extension. [Full documentation](docs/classutils.md)

#### `func.py`
Function decorators and composition utilities: compose, decompose, repeat, delay, suppresswarning, MultiMethod dispatch.

#### `iter.py`
Iterator utilities extending itertools: chunking, partitioning, windowing, flattening, grouping, and sequence operations.

#### `text.py`
Text processing: encoding fixes, camelCase conversion, fuzzy search, number parsing, truncation, base64 encoding, strtobool.

#### `format.py`
String formatting utilities for numbers, currency, time intervals, phone numbers, capitalization, and custom number formats.

#### `path.py`
Path operations: add to sys.path, get module directory, context manager for directory changes, script name extraction.

#### `dicts.py`
Dictionary utilities: inversion, key/value mapping, flattening, nested access, multikey sorting, comparison, tree operations.

#### `typing.py`
Type definitions for file-like objects, IO streams, and common data types used across the library.

#### `module.py`
Module management: dynamic importing, module patching, class instantiation, virtual modules, package discovery.

### Collection Classes (3 modules)

#### `attrdict.py`
Six dictionary classes with special behaviors:
- `attrdict`: Attribute-style access (dot notation)
- `lazydict`: Lazy evaluation of function values
- `emptydict`: Returns None for missing keys
- `bidict`: Bidirectional dictionary with inverse mapping
- `MutableDict`: Ordered dict with insert_before/insert_after
- `CaseInsensitiveDict`: Case-insensitive key access

#### `orderedset.py`
`OrderedSet`: Set that preserves insertion order with unique elements.

#### `heap.py`
`ComparableHeap`: Heap queue with custom comparator key function.

### I/O & System (5 modules)

#### `iolib.py`
I/O operations: CSV rendering, zipped CSV handling, iterable-to-stream conversion, JSON byteification, print suppression.

#### `stream.py`
Stream utilities: YAML/JSON conversion, binary/text handling, checksum calculation, stream decorators.

#### `proc.py`
Process utilities: finding processes by name/port, killing processes, process management.

#### `signals.py`
Signal handling: DelayedKeyboardInterrupt context manager, signal translation map.

#### `mime.py`
MIME type utilities for guessing file extensions and content types.

### Specialized Utilities (15 modules)

#### `webapp.py`
Web utilities: CORS (Flask/web.py), XSRF protection, authentication decorators, URL building, breadcrumb generation, HTML escaping, JSON encoders with ISO date support.

#### `stats.py`
Mathematical/statistical functions: average, variance, standard deviation, covariance, beta, combinatorics (choose), number parsing, threshold operations.

#### `sync.py`
Synchronization primitives: timeout decorator/context manager for thread/async operations.

#### `crypto.py`
Cryptography and encoding: base64 file encoding, hashing utilities.

#### `geo.py`
Geographic utilities: Mercator projection coordinate transformations (merc_x, merc_y).

#### `chart.py`
Plotting utilities for creating charts, particularly time series visualizations.

#### `dir.py`
Directory operations: recursive creation, temporary directories, file searching, safe moving, directory structure inspection, file downloading.

#### `exception.py`
Exception handling: print exceptions with traceback control, try_else wrapper for default values on failure.

#### `future.py`
Future pattern implementation for running functions asynchronously in separate threads.

#### `pandasutils.py`
Pandas utilities: interval-based operations, multi-column table display, downcast (memory optimization), fuzzymerge (fuzzy string matching for joins). Re-exports all pandas functionality.

#### `rand.py`
Random number generation with enhanced seeding, sampling, and distribution functions.

#### `thread.py`
Threading utilities: asyncd decorator, threaded decorator for background execution.

### Platform-Specific (1 module)

#### `win.py`
Windows utilities: command execution, psexec sessions, file share mounting, WMIC output parsing.

### Deprecated (1 module)

#### `util.py` ⚠️ **DEPRECATED**
This catch-all module has been broken up into specialized modules. All functions moved to appropriate locations. Import from top-level `libb` instead.

## Installation

The library uses Poetry for dependency management. Install with optional extras as needed:

```bash
# Clone the repository
git clone https://github.com/your-repo/libb.git
cd libb

# Install with Poetry (basic installation)
poetry install

# Install with specific extras
poetry install -E test      # Testing dependencies
poetry install -E pandas    # Pandas utilities
poetry install -E text      # Text processing (chardet, ftfy, rapidfuzz)
poetry install -E web       # Web utilities (Flask, web.py)
poetry install -E math      # Mathematical/plotting (numpy, matplotlib)

# Install all extras
poetry install --all-extras
```

Or install with pip:

```bash
pip install -e .
pip install -e ".[test,pandas,text,web,math]"  # with extras
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

Import utilities directly from the top-level `libb` package:

```python
from libb import Setting, compose, attrdict, timeout, fuzzy_search

# Configuration management
config = Setting()
config.database.host = 'localhost'
config.lock()

# Function composition
add_one = lambda x: x + 1
multiply_two = lambda x: x * 2
add_then_multiply = compose(multiply_two, add_one)
result = add_then_multiply(5)  # (5 + 1) * 2 = 12

# Attribute dictionaries
d = attrdict(x=10, y=20)
print(d.x)  # 10
d.z = 30

# Timeout decorator
@timeout(5)  # 5 second timeout
def slow_function():
    # ... long running operation
    pass

# Fuzzy string matching
items = [("Apple Inc", "AAPL"), ("Microsoft Corp", "MSFT")]
results = fuzzy_search("apple", items)
```

For more examples, see module-specific documentation and doctests.

## License

This project is licensed under the terms of the [LICENSE](LICENSE) file included
in the repository.
