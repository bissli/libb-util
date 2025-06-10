# ClassUtils Module Documentation

The `classutils` module provides a collection of utilities for working with classes, including decorators for singleton patterns, lazy evaluation, property delegation, and metaclass manipulation.

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [API Reference](#api-reference)
  - [attrs](#attrs)
  - [include](#include)
  - [singleton](#singleton)
  - [memoize](#memoize)
  - [classproperty](#classproperty)
  - [delegate](#delegate)
  - [lazy_property](#lazy_property)
  - [cachedstaticproperty](#cachedstaticproperty)
  - [staticandinstancemethod](#staticandinstancemethod)
  - [makecls](#makecls)
  - [extend_instance](#extend_instance)
  - [ultimate_type](#ultimate_type)
  - [catch_exception](#catch_exception)
  - [ErrorCatcher](#errorcatcher)
- [Usage Examples](#usage-examples)
- [Best Practices](#best-practices)

## Overview

The `classutils` module enhances Python's object-oriented programming capabilities by providing tools for:

- Creating property accessors for private attributes
- Implementing singleton patterns
- Caching expensive computations
- Delegating attribute access between objects
- Resolving metaclass conflicts
- Dynamic class modification at runtime

## Key Features

- **Property Generation**: Automatically create getters/setters for private attributes
- **Singleton Pattern**: Ensure only one instance of a class exists
- **Memoization**: Cache function results to avoid redundant computations
- **Lazy Evaluation**: Defer expensive computations until needed
- **Attribute Delegation**: Forward attribute access to composed objects
- **Metaclass Utilities**: Resolve metaclass conflicts and create custom metaclasses
- **Exception Handling**: Decorators for automatic exception catching and logging

## API Reference

### attrs

```python
attrs(*attrnames: str) -> None
```

Creates property getters/setters for private attributes that follow the `_name` convention.

**Parameters:**
- `*attrnames`: Names of attributes to create properties for (without underscore prefix)

**Example:**
```python
class Person:
    _name = "John"
    _age = 30
    attrs('name', 'age')

p = Person()
print(p.name)  # "John"
p.age = 31
print(p._age)  # 31
```

### include

```python
include(source: dict[str, Any], names: tuple[str, ...] = ()) -> None
```

Includes dictionary items as class attributes during class declaration.

**Parameters:**
- `source`: Dictionary containing attributes to include
- `names`: Optional tuple of specific attribute names to include (includes all if empty)

**Example:**
```python
config = {'debug': True, 'version': '1.0'}

class App:
    include(config)

print(App.debug)    # True
print(App.version)  # "1.0"
```

### singleton

```python
@singleton
class MyClass:
    pass
```

Decorator that enforces singleton pattern on a class. All calls to the class return the same instance.

**Example:**
```python
@singleton
class Database:
    def __init__(self):
        self.connected = False
    
    def connect(self):
        self.connected = True

db1 = Database()
db2 = Database()
print(db1 is db2)  # True
```

### memoize

```python
@memoize
def expensive_function(n):
    # Expensive computation
    return result
```

Decorator that caches function results based on arguments.

**Example:**
```python
@memoize
def fibonacci(n):
    if n < 2:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(100))  # Fast due to caching
```

### classproperty

```python
class MyClass:
    @classproperty
    def computed_value(cls):
        return cls.a + cls.b
```

Creates computed properties at the class level, similar to @property but for classes.

**Example:**
```python
class Config:
    base_url = "https://api.example.com"
    version = "v1"
    
    @classproperty
    def full_url(cls):
        return f"{cls.base_url}/{cls.version}"

print(Config.full_url)  # "https://api.example.com/v1"
```

### delegate

```python
delegate(deleg: str, attrs: str | list[str]) -> None
```

Delegates attribute access to another object, enabling composition over inheritance.

**Parameters:**
- `deleg`: Name of the attribute containing the delegate object
- `attrs`: Single attribute name or list of attribute names to delegate

**Example:**
```python
class Engine:
    def start(self):
        print("Engine started")
    
    def stop(self):
        print("Engine stopped")

class Car:
    engine = Engine()
    delegate('engine', ['start', 'stop'])

car = Car()
car.start()  # "Engine started"
```

### lazy_property

```python
@lazy_property
def expensive_property(self):
    # Expensive computation
    return result
```

Decorator that makes a property lazy-evaluated. The value is computed only once on first access.

**Example:**
```python
class DataProcessor:
    def __init__(self, data):
        self.data = data
    
    @lazy_property
    def processed_data(self):
        print("Processing data...")
        # Expensive processing
        return [x * 2 for x in self.data]

processor = DataProcessor([1, 2, 3])
# No processing yet
result1 = processor.processed_data  # "Processing data..."
result2 = processor.processed_data  # No print - cached
```

### cachedstaticproperty

```python
class MyClass:
    @cachedstaticproperty
    def expensive_constant():
        # Expensive computation
        return result
```

Combines @property and @staticmethod with caching. Computed once on first access.

**Example:**
```python
class MathConstants:
    @cachedstaticproperty
    def pi_squared():
        print("Computing pi squared...")
        import math
        return math.pi ** 2

print(MathConstants.pi_squared)  # "Computing pi squared..." then result
print(MathConstants.pi_squared)  # Just the result (cached)
```

### staticandinstancemethod

```python
class MyClass:
    @staticandinstancemethod
    def method(self, *args):
        if self is None:
            # Called as static method
        else:
            # Called as instance method
```

Allows a method to work as both static and instance method.

**Example:**
```python
class Logger:
    @staticandinstancemethod
    def log(self, message):
        prefix = "STATIC" if self is None else f"INSTANCE({id(self)})"
        print(f"[{prefix}] {message}")

Logger.log("Hello")        # "[STATIC] Hello"
logger = Logger()
logger.log("World")        # "[INSTANCE(...)] World"
```

### makecls

```python
makecls(*metas: type, **options: Any) -> Callable
```

Class factory that resolves metaclass conflicts automatically.

**Parameters:**
- `*metas`: Explicit metaclasses to use
- `**options`: Options like `priority` to control metaclass precedence

**Example:**
```python
class MetaA(type):
    pass

class MetaB(type):
    pass

class A(metaclass=MetaA):
    pass

class B(metaclass=MetaB):
    pass

# This would normally fail with metaclass conflict
class C(A, B, metaclass=makecls()):
    pass
```

### extend_instance

```python
extend_instance(obj: object, cls: type, left: bool = True) -> None
```

Dynamically extends an instance's class hierarchy at runtime.

**Parameters:**
- `obj`: The instance to extend
- `cls`: The class to mix into the instance's hierarchy
- `left`: If True, adds cls with higher precedence; if False, lower precedence

**Example:**
```python
class Serializable:
    def to_json(self):
        import json
        return json.dumps(self.__dict__)

class Person:
    def __init__(self, name):
        self.name = name

p = Person("Alice")
extend_instance(p, Serializable)
print(p.to_json())  # '{"name": "Alice"}'
```

### ultimate_type

```python
ultimate_type(typeobj: object | type | None) -> type
```

Finds the ultimate non-object base class in an inheritance hierarchy.

**Parameters:**
- `typeobj`: An object, type, or None to analyze

**Example:**
```python
import datetime

class CustomDate(datetime.date):
    pass

class SpecialDate(CustomDate):
    pass

d = SpecialDate(2023, 1, 1)
print(ultimate_type(d))  # <class 'datetime.date'>
```

### catch_exception

```python
@catch_exception
def risky_function():
    # Code that might raise exceptions
    pass

# Or with custom log level
@catch_exception(level=logging.ERROR)
def critical_function():
    pass
```

Decorator that catches and logs exceptions without re-raising them.

**Parameters:**
- `level`: Logging level for exception details (default: logging.DEBUG)

**Example:**
```python
@catch_exception
def divide(a, b):
    return a / b

result = divide(10, 0)  # Logs exception, returns None
print(result)  # None
```

### ErrorCatcher

```python
class MyClass(metaclass=ErrorCatcher):
    _error_log_level = logging.WARNING  # Optional
    
    def method(self):
        # All methods automatically catch exceptions
        pass
```

Metaclass that wraps all methods with exception catching.

**Example:**
```python
class SafeCalculator(metaclass=ErrorCatcher):
    def divide(self, a, b):
        return a / b
    
    def sqrt(self, n):
        return n ** 0.5

calc = SafeCalculator()
print(calc.divide(10, 0))  # None (exception logged)
print(calc.sqrt(16))       # 4.0
```

## Usage Examples

### Creating a Configuration Class

```python
class Config:
    _debug = False
    _api_key = None
    _timeout = 30
    
    attrs('debug', 'api_key', 'timeout')
    
    @classproperty
    def is_production(cls):
        return not cls._debug

config = Config()
config.debug = True
print(Config.is_production)  # False
```

### Building a Cached Data Service

```python
@singleton
class DataService:
    def __init__(self):
        self._cache = {}
    
    @memoize
    def fetch_user(self, user_id):
        print(f"Fetching user {user_id}")
        # Simulate expensive API call
        return {"id": user_id, "name": f"User{user_id}"}
    
    @lazy_property
    def connection(self):
        print("Establishing connection...")
        # Simulate expensive connection setup
        return "Connected"

service = DataService()
user1 = service.fetch_user(1)  # "Fetching user 1"
user1_again = service.fetch_user(1)  # No print - cached
```

### Implementing a Plugin System

```python
class Plugin:
    def execute(self):
        raise NotImplementedError

class LoggingMixin:
    def log(self, message):
        print(f"[{self.__class__.__name__}] {message}")

class MyPlugin(Plugin):
    def execute(self):
        return "Plugin executed"

# Add logging capability at runtime
plugin = MyPlugin()
extend_instance(plugin, LoggingMixin)
plugin.log("Starting execution")
result = plugin.execute()
plugin.log(f"Result: {result}")
```

## Best Practices

1. **Use `attrs` for Clean APIs**: When you have private attributes that need public access, use `attrs` instead of writing repetitive property definitions.

2. **Singleton with Caution**: Use the `@singleton` decorator sparingly. It's useful for resources like database connections or configuration objects, but can make testing difficult.

3. **Memoization for Pure Functions**: `@memoize` works best with pure functions (same input always produces same output). Avoid using it with functions that have side effects.

4. **Lazy Properties for Expensive Operations**: Use `@lazy_property` for attributes that are expensive to compute but don't change after initialization.

5. **Delegation Over Inheritance**: Use `delegate` to compose objects rather than creating deep inheritance hierarchies.

6. **Exception Handling**: Use `@catch_exception` or `ErrorCatcher` for non-critical operations where you want graceful degradation rather than crashes.

7. **Metaclass Conflicts**: When dealing with multiple inheritance and metaclass conflicts, use `makecls()` to automatically resolve them.

8. **Runtime Class Modification**: Use `extend_instance` sparingly and document it well, as it can make code harder to understand.

Remember that while these utilities provide powerful capabilities, they should be used judiciously to maintain code clarity and maintainability.
