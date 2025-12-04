# libb-util

[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://bissli.github.io/libb-util/)

![libb](https://raw.githubusercontent.com/bissli/libb-util/refs/heads/master/bissli.jpg "Bissli - via wikipedia https://en.wikipedia.org/wiki/Bissli")

A comprehensive collection of utility functions and classes for Python.

## Installation

```bash
pip install libb-util

# Or with extras
pip install "libb-util[pandas,text,web,math]"
```

## Quick Start

Always import from the top-level `libb` package:

```python
from libb import Setting, compose, attrdict, timeout

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

## Documentation

Full documentation is available at **[bissli.github.io/libb-util](https://bissli.github.io/libb-util/)**:

- [Installation](https://bissli.github.io/libb-util/installation.html)
- [Quick Start Guide](https://bissli.github.io/libb-util/quickstart.html)
- [API Reference](https://bissli.github.io/libb-util/api/index.html)

## License

See [LICENSE](LICENSE) file.
