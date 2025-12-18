# libb-util

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://bissli.github.io/libb-util/)

![libb](https://raw.githubusercontent.com/bissli/libb-util/refs/heads/master/bissli.jpg "Bissli - via wikipedia https://en.wikipedia.org/wiki/Bissli")

Python utility library with Rust-accelerated functions for text processing, iteration, dictionary sorting, and number parsing.

```bash
pip install libb-util
```

## Quick Reference

```python
from libb import Setting, compose, attrdict, timeout
from libb import multikeysort, numify, parse

# Configuration with dot notation
config = Setting()
config.database.host = 'localhost'
config.lock()

# Function composition
add_then_multiply = compose(lambda x: x * 2, lambda x: x + 1)
result = add_then_multiply(5)  # (5 + 1) * 2 = 12

# Attribute dictionary
d = attrdict(x=10, y=20)
print(d.x)  # 10

# Timeout decorator
@timeout(5)
def slow_function():
    pass
```

---

## Installation

```bash
pip install libb-util

# With extras
pip install "libb-util[pandas,text,web,math]"
```

### Available Extras

| Extra | Description |
|-------|-------------|
| `pandas` | DataFrame utilities with pyarrow |
| `text` | Text processing (ftfy, rapidfuzz, chardet) |
| `web` | Web frameworks (Flask, Twisted, web.py) |
| `math` | Matplotlib charting |
| `test` | Testing tools (pytest, asserts) |
| `docs` | Sphinx documentation |

---

## Core Modules

### Configuration

| Function/Class | Description |
|----------------|-------------|
| `Setting()` | Hierarchical config with dot notation and locking |
| `attrdict(**kw)` | Dict with attribute access |
| `dictobj(**kw)` | Immutable dict with attribute access |

### Function Utilities

| Function | Description |
|----------|-------------|
| `compose(*funcs)` | Right-to-left function composition |
| `timeout(seconds)` | Decorator to limit function execution time |
| `retry(tries, delay)` | Decorator for retry with exponential backoff |
| `memoize(func)` | Cache function results |
| `once(func)` | Execute function only once |

### Dictionary Operations (Rust-accelerated)

| Function | Description |
|----------|-------------|
| `multikeysort(items, columns)` | Sort list of dicts by multiple keys |
| `numify(val, to=int)` | Convert string to number with format handling |
| `parse(s)` | Extract number from string |

```python
# Rust-accelerated sorting
data = [{'name': 'Alice', 'age': 30}, {'name': 'Bob', 'age': 25}]
multikeysort(data, ['age', '-name'])  # Sort by age asc, name desc

# Number parsing handles accounting formats
parse('1,200')      # 1200
parse('(500)')      # -500  (accounting negative)
parse('100.5%')     # 100.5
```

### Iteration (Rust-accelerated)

| Function | Description |
|----------|-------------|
| `chunked(iterable, n)` | Split into chunks of size n |
| `collapse(*args)` | Recursively flatten nested lists/tuples ⚡ |
| `backfill(values)` | Fill None values with last non-None ⚡ |
| `backfill_iterdict(iterdict)` | Back-fill dicts with latest values per key ⚡ |
| `same_order(ref, comp)` | Check if elements appear in same order ⚡ |
| `unique(iterable)` | Unique items preserving order |

⚡ = Rust-accelerated

### Text Processing (Rust-accelerated)

| Function | Description |
|----------|-------------|
| `sanitize_vulgar_string(s)` | Replace vulgar fractions with decimals ⚡ |
| `uncamel(camel)` | Convert CamelCase to snake_case ⚡ |
| `underscore_to_camelcase(s)` | Convert snake_case to camelCase ⚡ |
| `normalize(text)` | Unicode normalization |
| `slugify(text)` | URL-safe slug |
| `strip_html(text)` | Remove HTML tags |
| `truncate(text, length)` | Truncate with ellipsis |

⚡ = Rust-accelerated

### I/O and Paths

| Function | Description |
|----------|-------------|
| `ensure_dir(path)` | Create directory if not exists |
| `safe_filename(name)` | Sanitize filename |
| `temp_file(**kw)` | Context manager for temp files |
| `atomic_write(path)` | Atomic file write context |

### Concurrency

| Function | Description |
|----------|-------------|
| `threaded(func)` | Run function in thread |
| `parallel_map(func, items)` | Parallel execution |
| `Semaphore(n)` | Limit concurrent access |

### Process Management

| Function | Description |
|----------|-------------|
| `run_cmd(cmd)` | Execute shell command |
| `is_running(pid)` | Check if process exists |
| `kill_tree(pid)` | Kill process and children |

---

## Classes

### OrderedSet

Set that maintains insertion order:

```python
from libb import OrderedSet

s = OrderedSet([1, 2, 3, 2, 1])
list(s)  # [1, 2, 3]
```

### Heap

Min/max heap implementations:

```python
from libb import MinHeap, MaxHeap

h = MinHeap([3, 1, 4, 1, 5])
h.pop()  # 1
```

---

## Documentation

Full documentation at **[bissli.github.io/libb-util](https://bissli.github.io/libb-util/)**:

- [Installation](https://bissli.github.io/libb-util/installation.html)
- [Quick Start Guide](https://bissli.github.io/libb-util/quickstart.html)
- [API Reference](https://bissli.github.io/libb-util/api/index.html)

---

## Development

```bash
# Install dev dependencies
pip install -e ".[test,docs]"

# Build Rust extension
maturin develop

# Run tests
pytest
```

## License

See [LICENSE](LICENSE) file.
