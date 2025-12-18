from __future__ import annotations

import logging
import sys
import weakref
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)

P = ParamSpec('P')
R = TypeVar('R')

__all__ = [
    'attrs',
    'include',
    'singleton',
    'memoize',
    'classproperty',
    'delegate',
    'lazy_property',
    'cachedstaticproperty',
    'staticandinstancemethod',
    'metadict',
    'makecls',
    'extend_instance',
    'ultimate_type',
    'catch_exception',
    'ErrorCatcher',
]


def attrs(*attrnames: str) -> None:
    """Create property getters/setters for private attributes.

    Automatically generates property accessors for attributes that follow
    the _name convention, allowing clean access to private attributes.

    :param attrnames: Names of attributes to create properties for (without underscore prefix).

    Basic Usage::

        >>> class Foo:
        ...     _a = 1
        ...     _b = 2
        ...     _c = 3
        ...     _z = (_a, _b, _c)
        ...     attrs('a', 'b', 'c', 'z')
        >>> f = Foo()
        >>> f.a
        1
        >>> f.a+f.b==f.c
        True

    Setter Functionality::

        >>> f.a = 2
        >>> f.a==f._a==2
        True

    Lazy Definitions::

        >>> len(f.z)==3
        True
        >>> sum(f.z)==6
        True
        >>> f.z[0]==f._z[0]==1
        True
        >>> f.z = (4, 5, 6,)
        >>> sum(f.z)
        15
        >>> f.a==2
        True
    """
    def _makeprop(name):
        _get = lambda self: getattr(self, f'_{name}')
        _set = lambda self, value: setattr(self, f'_{name}', value)
        return property(_get, _set)

    caller_locals = sys._getframe(1).f_locals
    for attrname in attrnames:
        caller_locals[attrname] = _makeprop(attrname)


def include(source: dict[str, Any], names: tuple[str, ...] = ()) -> None:
    """Include dictionary items as class attributes during class declaration.

    Injects dictionary key-value pairs into the calling class namespace,
    optionally filtering by specific names.

    :param dict source: Dictionary containing attributes to include.
    :param tuple names: Optional tuple of specific attribute names to include (includes all if empty).

    Include All Attributes::

        >>> d = dict(x=10, y='foo')
        >>> class Foo:
        ...     include(d)
        >>> Foo.x
        10
        >>> Foo.y
        'foo'

    Include Specific Attributes::

        >>> class Boo:
        ...     include(d, ('y',))
        >>> hasattr(Boo, 'x')
        False
        >>> hasattr(Boo, 'y')
        True
    """
    sys._getframe(1).f_locals.update({name: source[name] for name in names} if names else source)


def singleton(cls: type) -> object:
    """Decorator that enforces singleton pattern on a class.

    Ensures only one instance of the decorated class can exist.
    All calls to the class return the same instance.

    :param type cls: The class to convert to a singleton.
    :returns: The single instance of the class.

    Basic Usage::

        >>> @singleton
        ... class Foo:
        ...     _x = 100
        ...     _y = 'y'
        ...     attrs('x', 'y')
        >>> F = Foo
        >>> F() is F() is F
        True
        >>> id(F()) == id(F())
        True

    Shared State::

        >>> f = F()
        >>> f.x == F().x == f.x == 100
        True
        >>> F.x = 50
        >>> f.x == F().x == F.x == 50
        True

    Deep Copy Behavior::

        >>> import copy
        >>> fc = copy.deepcopy(f)
        >>> FC = copy.deepcopy(F)
        >>> fc.y==f.y==F.y==FC.y=='y'
        True
    """
    obj = cls()
    obj.__class__ = type(obj.__class__.__name__, (obj.__class__,), {})
    obj.__class__.__call__ = lambda x: x
    return obj


def memoize(obj: Callable[P, R]) -> Callable[P, R]:
    """Decorator that caches function results based on arguments.

    Stores function call results in a cache dictionary attached to the
    function itself, avoiding redundant computations for repeated calls
    with the same arguments.

    :param obj: The function to memoize.
    :returns: A wrapped function with caching behavior.

    Basic Usage::

        >>> def n_with_sum_k(n, k):
        ...     if n==0:
        ...         return 0
        ...     elif k==0:
        ...         return 1
        ...     else:
        ...         less_n = n_with_sum_k(n-1, k)
        ...         less_k = n_with_sum_k(n, k-1)
        ...         less_both = n_with_sum_k(n-1, k-1)
        ...         return less_n + less_k + less_both

    Memoization Speeds Up Recursive Calls::

        >>> n_with_sum_k_mz = memoize(n_with_sum_k)
        >>> n_with_sum_k_mz(3, 5)
        61
        >>> n_with_sum_k_mz.cache
        {((3, 5), ()): 61}
    """

    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args: P.args, **kwargs: P.kwargs) -> R:
        key = (args, tuple(sorted(kwargs.items())))
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]

    return memoizer


class classproperty(property):
    """Decorator that creates computed properties at the class level.

    Similar to @property but works on classes rather than instances,
    allowing dynamic class-level attributes.

    Basic Usage::

        >>> class Foo:
        ...     include(dict(a=1, b=2))
        ...     @classproperty
        ...     def c(cls):
        ...         return cls.a+cls.b
        >>> Foo.a
        1
        >>> Foo.b
        2
        >>> Foo.c
        3

    Dynamic Updates::

        >>> Foo.a = 2
        >>> Foo.c
        4
    """

    def __get__(desc, self, cls):
        return desc.fget(cls)


def delegate(deleg: str, attrs: str | list[str]) -> None:
    """Delegate attribute access to another object.

    Creates properties that forward attribute access to a specified
    delegate object, enabling composition over inheritance.

    :param str deleg: Name of the attribute containing the delegate object.
    :param attrs: Single attribute name or list of attribute names to delegate.
    :type attrs: str or list[str]

    Delegate Simple Attributes::

        >>> class X:
        ...     a = 1
        >>> class Y:
        ...     x = X()
        ...     delegate('x', 'a')
        >>> Y().a
        1

    Delegate Methods::

        >>> class A:
        ...     def echo(self, x):
        ...         print(x)
        >>> class B:
        ...     a = A()
        ...     delegate('a', ['echo'])
        >>> B().echo('whoa!')
        whoa!
    """

    def _makeprop(attr):
        return property(lambda self: getattr(getattr(self, deleg), attr))

    caller_locals = sys._getframe(1).f_locals
    if isinstance(attrs, str):
        attrs = [attrs]
    for attr in attrs:
        caller_locals[attr] = _makeprop(attr)


def lazy_property(fn: Callable[[Any], R]) -> property:
    """Decorator that makes a property lazy-evaluated.

    Computes the property value only once on first access, then caches
    the result for subsequent accesses. Useful for expensive computations.

    :param fn: The property method to make lazy.
    :returns: A lazy property descriptor.

    Basic Lazy Evaluation::

        >>> import time
        >>> class Sloth:
        ...     def _slow_cool(self, n):
        ...         time.sleep(n)
        ...         return n**2
        ...     @lazy_property
        ...     def slow(self):
        ...         return True
        ...     @lazy_property
        ...     def cool(self):
        ...         return self._slow_cool(3)

    Instantiation is Fast::

        >>> x = time.time()
        >>> s = Sloth()
        >>> time.time()-x < 1
        True
        >>> time.time()-x < 1
        True

    First Access Triggers Computation::

        >>> hasattr(s, '_lazy_slow')
        False
        >>> s.slow
        True
        >>> hasattr(s, '_lazy_slow')
        True

    Expensive Computation Happens Once::

        >>> s.cool
        9
        >>> 3 < time.time()-x < 6
        True
        >>> s.cool
        9
        >>> 3 < time.time()-x < 6
        True
    """
    attr_name = '_lazy_' + fn.__name__

    @property
    def _lazy_property(self):
        if not hasattr(self, attr_name):
            setattr(self, attr_name, fn(self))
        return getattr(self, attr_name)

    @_lazy_property.deleter
    def _lazy_property(self):
        if hasattr(self, attr_name):
            delattr(self, attr_name)

    return _lazy_property


class cachedstaticproperty:
    """Decorator combining @property and @staticmethod with caching.

    Creates a class-level property that is computed once on first access
    and cached for subsequent accesses.

    Basic Usage (expensive computation runs only once)::

        >>> def somecalc():
        ...     print('Running somecalc...')
        ...     return 1
        >>> class Foo:
        ...    @cachedstaticproperty
        ...    def somefunc():
        ...        return somecalc()
        >>> Foo.somefunc
        Running somecalc...
        1
        >>> Foo.somefunc
        1
    """
    def __init__(self, func):
        self.func = func

    def __get__(self, inst, owner):
        result = self.func()
        setattr(owner, self.func.__name__, result)
        return result


class staticandinstancemethod:
    """Decorator allowing a method to work as both static and instance method.

    When called on the class, self is None. When called on an instance,
    self is the instance.

    Basic Usage (dual behavior)::

        >>> class Foo:
        ...     @staticandinstancemethod
        ...     def bar(self, x, y):
        ...         print(self is None and "static" or "instance")
        >>> Foo.bar(1,2)
        static
        >>> Foo().bar(1,2)
        instance
    """
    def __init__(self, f):
        self.f = f

    def __get__(self, obj, klass=None):
        def newfunc(*args, **kw):
            return self.f(obj, *args, **kw)
        return newfunc


#: Cache for generated metaclasses to avoid redundant class creation.
metadict = weakref.WeakValueDictionary()


def _generatemetaclass(bases: tuple[type, ...], metas: tuple[type, ...], priority: bool) -> type:
    trivial = lambda m: sum((issubclass(M, m) for M in metas), m is type)
    metabs = tuple(mb for mb in map(type, bases) if not trivial(mb))
    metabases = (metabs + metas, metas + metabs)[priority]

    if metabases in metadict:
        return metadict[metabases]

    if not metabases:
        meta = type
    elif len(metabases) == 1:
        meta = metabases[0]
    else:
        metaname = '_' + ''.join([m.__name__ for m in metabases])
        meta = makecls()(metaname, metabases, {})

    return metadict.setdefault(metabases, meta)


def makecls(*metas: type, **options: Any) -> Callable[[str, tuple[type, ...], dict[str, Any]], type]:
    """Class factory that resolves metaclass conflicts automatically.

    When multiple inheritance involves conflicting metaclasses, this factory
    generates a compatible metaclass that inherits from all necessary metaclasses.

    :param metas: Explicit metaclasses to use.
    :param options: Keyword options:

        - **priority**: If True, given metaclasses take precedence over base metaclasses.

    :returns: A class factory function that creates classes with resolved metaclasses.

    Metaclass Conflict Resolution::

        >>> class M_A(type):
        ...     pass
        >>> class M_B(type):
        ...     pass
        >>> class A(metaclass=M_A):
        ...     pass
        >>> class B(metaclass=M_B):
        ...     pass

    Normal Inheritance Fails::

        >>> class C(A,B):
        ...     pass
        Traceback (most recent call last):
        ...
        TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases

    Using makecls Resolves the Conflict::

        >>> class C(A,B,metaclass=makecls()):
        ...    pass
        >>> (C, C.__class__)
        (<class '....C'>, <class '...._M_AM_B'>)

    Metaclass Caching::

        >>> class D(A,B,metaclass=makecls()):
        ...    pass
        >>> (D, D.__class__)
        (<class '....D'>, <class '...._M_AM_B'>)
        >>> C.__class__ is D.__class__
        True
    """
    priority = options.get('priority', False)
    return lambda n, b, d: _generatemetaclass(b, metas, priority)(n, b, d)


def extend_instance(obj: object, cls: type, left: bool = True) -> None:
    """Dynamically extend an instance's class hierarchy at runtime.

    Modifies an object's class to include additional base classes,
    effectively adding mixins or extending functionality after instantiation.

    :param object obj: The instance to extend.
    :param type cls: The class to mix into the instance's hierarchy.
    :param bool left: If True, adds cls with higher precedence; if False, lower precedence.

    Method Resolution Order Demonstration::

        >>> from pprint import pprint
        >>> class X:pass
        >>> class Y: pass
        >>> class Z:pass
        >>> class A(X,Y):pass
        >>> class B(A,Y,Z):pass
        >>> class F(B): pass
        >>> pprint(F.mro())
        [<class '....F'>,
         <class '....B'>,
         <class '....A'>,
         <class '....X'>,
         <class '....Y'>,
         <class '....Z'>,
         <class 'object'>]

    Left Precedence (higher priority)::

        >>> class F_L:
        ...     def __init__(self):
        ...         extend_instance(self, B, left=True)
        >>> f_l = F_L()
        >>> pprint(f_l.__class__.__mro__)
        (<class '....F_L'>,
         <class '....B'>,
         <class '....A'>,
         <class '....X'>,
         <class '....Y'>,
         <class '....Z'>,
         <class '....F_L'>,
         <class 'object'>)

    Right Precedence (lower priority)::

        >>> class F_R:
        ...     def __init__(self):
        ...         extend_instance(self, B, left=False)
        >>> f_r = F_R()
        >>> pprint(f_r.__class__.__mro__)
        (<class '....F_R'>,
         <class '....F_R'>,
         <class '....B'>,
         <class '....A'>,
         <class '....X'>,
         <class '....Y'>,
         <class '....Z'>,
         <class 'object'>)
    """
    if left:
        obj.__class__ = type(obj.__class__.__name__, (cls, obj.__class__), {})
    else:
        obj.__class__ = type(obj.__class__.__name__, (obj.__class__, cls), {})


def ultimate_type(typeobj: object | type | None) -> type:
    """Find the ultimate non-object base class in an inheritance hierarchy.

    Traverses the inheritance chain to find the most fundamental base class
    that isn't 'object' itself. Useful for identifying the core type of
    subclassed objects.

    :param typeobj: An object, type, or None to analyze.
    :returns: The ultimate base type (excluding object).
    :rtype: type

    Finding Base Types::

        >>> import datetime
        >>> class DateFoo(datetime.date):
        ...     pass
        >>> class DateBar(DateFoo):
        ...    pass
        >>> d0 = datetime.date(2000, 1, 1)
        >>> d1 = DateFoo(2000, 1, 1)
        >>> d2 = DateBar(2000, 1, 1)
        >>> ultimate_type(d0)
        <class 'datetime.date'>
        >>> ultimate_type(d1)
        <class 'datetime.date'>
        >>> ultimate_type(d1)
        <class 'datetime.date'>
        >>> ultimate_type(d1.__class__)
        <class 'datetime.date'>
        >>> ultimate_type(d2.__class__)
        <class 'datetime.date'>

    Special Cases::

        >>> ultimate_type(None)
        <class 'NoneType'>
        >>> ultimate_type(object)
        <class 'object'>
    """
    if not isinstance(typeobj, type):
        typeobj = type(typeobj)
    bases, this = [typeobj], typeobj
    while True:
        if hasattr(this, '__bases__') and this.__bases__:
            bases.append(this.__bases__[-1])
            this = bases[-1]
        else:
            break
    if len(bases) > 1:
        return bases[-2]
    return bases[0]


def catch_exception(f: Callable[P, R] | None = None, *, level: int = logging.DEBUG) -> Callable[[Callable[P, R]], Callable[P, R]] | Callable[P, R | None]:
    """Decorator that catches and reports exceptions without re-raising.

    Can be used with or without parameters to specify the logging level.

    :param f: Function to wrap with exception handling (when used without parameters).
    :param int level: Logging level for exception details (default: logging.DEBUG).
    :returns: Wrapped function that prints exceptions instead of raising them.

    Default Usage (DEBUG level)::

        >>> @catch_exception
        ... def divide(x, y):
        ...     return x / y
        >>> divide(1, 0) is None
        True

    Specifying Log Level::

        >>> @catch_exception(level=logging.ERROR)
        ... def risky_operation():
        ...     raise ValueError("Something went wrong")
        >>> risky_operation() is None
        True
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R | None]:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(level, f'Caught exception in {func.__name__}: {type(e).__name__}: {e}')
        return wrapper

    if f is None:
        return decorator
    else:
        return decorator(f)


class ErrorCatcher(type):
    """Metaclass that wraps all methods with exception catching.

    Automatically applies exception handling to all callable attributes
    of a class, preventing exceptions from propagating. Can optionally
    specify the logging level for all wrapped methods via the
    ``_error_log_level`` class attribute.

    Automatic Exception Handling::

        >>> import logging
        >>> logging.getLogger(__name__).setLevel(logging.CRITICAL)
        >>> class Test(metaclass=ErrorCatcher):
        ...     def __init__(self, val):
        ...         self.val = val
        ...     def calc(self):
        ...         return self.val / 0
        >>> t = Test(5)
        >>> t.calc() is None
        True

    With Custom Log Level::

        >>> class TestWithLevel(metaclass=ErrorCatcher):
        ...     _error_log_level = logging.ERROR
        ...     def risky(self):
        ...         raise RuntimeError("Oops")
        >>> t2 = TestWithLevel()
        >>> t2.risky() is None
        True
    """
    def __new__(cls, name, bases, dct):
        log_level = dct.get('_error_log_level', logging.DEBUG)
        for m in dct:
            if callable(dct[m]) and not m.startswith('_'):
                dct[m] = catch_exception(dct[m], level=log_level)
        return type.__new__(cls, name, bases, dct)


if __name__ == '__main__':
    logging.getLogger(__name__).setLevel(logging.CRITICAL)
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
