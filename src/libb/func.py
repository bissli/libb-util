import ast
import inspect
import logging
import sys
import warnings
from collections.abc import Iterable
from functools import reduce, wraps
from time import time

logger = logging.getLogger(__name__)

__all__ = [
    'is_instance_method',
    'find_decorators',
    'compose',
    'composable',
    'copydoc',
    'get_calling_function',
    'repeat',
    'timing',
    'suppresswarning',
    'MultiMethod',
    'multimethod',
    ]


def is_instance_method(func):
    """Check if a function is an instance method.

    :param func: Function to check.
    :returns: True if function is an instance method.
    :rtype: bool

    Example::

        >>> class MyClass:
        ...     def my_method(self):
        ...         pass
        >>> def my_function():
        ...     pass
        >>> is_instance_method(MyClass.my_method)
        True
        >>> is_instance_method(my_function)
        False
    """
    return len(func.__qualname__.split('.')) > 1


def find_decorators(target):
    """Find decorators applied to functions in a target module/class.

    :param target: Module or class to inspect.
    :returns: Dictionary mapping function names to decorator AST representations.
    :rtype: dict

    Example::

        >>> class Example:  # doctest: +SKIP
        ...     @staticmethod
        ...     def static_method():
        ...         pass
        >>> decorators = find_decorators(Example)  # doctest: +SKIP
        >>> 'static_method' in decorators  # doctest: +SKIP
        True

    .. note::
        Algorithm from https://stackoverflow.com/a/9580006
    """
    res = {}

    def visit_function_def(node):
        res[node.name] = [ast.dump(e) for e in node.decorator_list]

    V = ast.NodeVisitor()
    V.visit_FunctionDef = visit_function_def
    V.visit(compile(inspect.getsource(target), '?', 'exec', ast.PyCF_ONLY_AST))
    return res


def compose(*functions):
    """Return a function folding over a list of functions.

    Each arg must have a single param.

    :param functions: Functions to compose.
    :returns: Composed function.

    Example::

        >>> f = lambda x: x+4
        >>> g = lambda y: y/2
        >>> h = lambda z: z*3
        >>> fgh = compose(f, g, h)

    Beware of order for non-commutative functions (first in, **last** out)::

        >>> fgh(2)==h(g(f(2)))
        False
        >>> fgh(2)==f(g(h(2)))
        True
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)


def composable(decorators):
    """Decorator that takes a list of decorators to be composed.

    Useful when list of decorators starts getting large and unruly.

    :param decorators: List of decorators to compose.
    :returns: Composed decorator.

    Setup::

        >>> def m3(func):
        ...     def wrapped(n):
        ...         return func(n)*3.
        ...     return wrapped
        >>> def d2(func):
        ...     def wrapped(n):
        ...         return func(n)/2.
        ...     return wrapped
        >>> def p3(n):
        ...     return n+3.
        >>> @m3
        ... @d2
        ... def plusthree(x):
        ...     return p3(x)
        >>> @composable([d2, m3])
        ... def cplusthree(x):
        ...     return p3(x)

    Note: composed decorators are not interchangeable with ``compose``::

        >>> func = compose(m3, d2, p3)(4)
        >>> hasattr(func, '__call__')
        True
        >>> compose(lambda n: n*3., lambda n: n/2., p3)(4)
        10.5

    What they do allow is consolidating longer decorator chains::

        >>> plusthree(4)
        10.5
        >>> cplusthree(4)
        10.5
    """

    def composed(func):
        if isinstance(decorators, Iterable) and not isinstance(decorators, str):
            for dec in decorators[::-1]:
                func = dec(func)
            return func
        return decorators(func)

    def wrapped(func):
        @wraps(func)
        def f(*a, **kw):
            return composed(func)(*a, **kw)
        return f

    return wrapped


def copydoc(fromfunc, sep='\n', basefirst=True):
    """Decorator to copy the docstring of another function.

    :param fromfunc: Function to copy docstring from.
    :param str sep: Separator between docstrings.
    :param bool basefirst: If True, base docstring comes first.
    :returns: Decorator function.

    Example::

        >>> class A():
        ...     def myfunction():
        ...         '''Documentation for A.'''
        ...         pass
        >>> class B(A):
        ...     @copydoc(A.myfunction)
        ...     def myfunction():
        ...         '''Extra details for B.'''
        ...         pass
        >>> class C(A):
        ...     @copydoc(A.myfunction, basefirst=False)
        ...     def myfunction():
        ...         '''Extra details for B.'''
        ...         pass

    Do not activate doctests::

        >>> class D():
        ...     def myfunction():
        ...         '''.>>> 2 + 2 = 5'''
        ...         pass
        >>> class E(D):
        ...     @copydoc(D.myfunction)
        ...     def myfunction():
        ...         '''Extra details for E.'''
        ...         pass
        >>> help(B.myfunction)
        Help on function myfunction in module ...:
        <BLANKLINE>
        myfunction()
            Documentation for A.
            Extra details for B.
        <BLANKLINE>
        >>> help(C.myfunction)
        Help on function myfunction in module ...:
        <BLANKLINE>
        myfunction()
            Extra details for B.
            Documentation for A.
        <BLANKLINE>
        >>> help(E.myfunction)
        Help on function myfunction in module ...:
        <BLANKLINE>
        myfunction()
            .>>> 2 + 2 = 5 # doctest: +DISABLE
            Extra details for E.
        <BLANKLINE>
    """

    def _disable_doctest(docstr):
        lines = []
        for line in docstr.splitlines():
            if '>>>' in line:
                line += ' # doctest: +DISABLE'
            lines.append(line)
        return '\n'.join(lines)

    def _decorator(func):
        sourcedoc = _disable_doctest(fromfunc.__doc__)
        if func.__doc__ is None:
            func.__doc__ = sourcedoc
        else:
            order = [sourcedoc, func.__doc__] if basefirst else [func.__doc__, sourcedoc]
            func.__doc__ = sep.join(order)
        return func

    return _decorator


def get_calling_function():
    """Find the calling function in many common cases.

    :returns: The calling function object.
    :raises AttributeError: If function cannot be found.

    .. seealso::
        See ``tests/test_func.py`` for usage examples.
    """
    fr = sys._getframe(1)   # inspect.stack()[1][0]
    co = fr.f_code
    for get in (
        lambda: fr.f_globals[co.co_name],
        lambda: getattr(fr.f_locals['self'], co.co_name),
        lambda: getattr(fr.f_locals['cls'], co.co_name),
        lambda: fr.f_back.f_locals[co.co_name],  # nested
        lambda: fr.f_back.f_locals['func'],  # decorators
        lambda: fr.f_back.f_locals['meth'],
        lambda: fr.f_back.f_locals['f'],
    ):
        try:
            func = get()
        except (KeyError, AttributeError):
            pass
        else:
            if func.__code__ == co:
                return func
    raise AttributeError('func not found')


def repeat(x_times=2):
    """Decorator to repeat a function multiple times.

    :param int x_times: Number of times to repeat (default: 2).
    :returns: Decorator function.

    Example::

        >>> @repeat(3)
        ... def printme():
        ...    print('Foo')
        ...    return 'Bar'
        >>> printme()
        Foo
        Foo
        Foo
        'Bar'
    """

    def wrapper(func):
        @wraps(func)
        def wrapped_fn(*args, **kwargs):
            times = 0
            while times < x_times:
                result = func(*args, **kwargs)
                times += 1
            return result
        return wrapped_fn
    return wrapper


def timing(func):
    """Decorator to log function execution time.

    :param func: Function to time.
    :returns: Wrapped function that logs execution time.

    Example::

        >>> @timing  # doctest: +SKIP
        ... def slow_function():
        ...     import time
        ...     time.sleep(0.01)
        ...     return 42
        >>> result = slow_function()  # doctest: +SKIP
        >>> result  # doctest: +SKIP
        42
    """
    @wraps(func)
    def wrap(*args, **kw):
        ts = time()
        result = func(*args, **kw)
        te = time()
        logger.debug(f'func:{func.__name__!r} args:[{args!r}, {kw!r}] took: {te-ts:2.4f} sec')
        return result
    return wrap


def suppresswarning(func):
    """Decorator to suppress warnings during function execution.

    :param func: Function to wrap.
    :returns: Wrapped function that suppresses warnings.

    Example::

        >>> import warnings
        >>> @suppresswarning
        ... def noisy_function():
        ...     warnings.warn("This warning is suppressed")
        ...     return "done"
        >>> noisy_function()
        'done'
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return func(*args, **kwargs)
    return wrapper


registry = {}


class MultiMethod:
    """Multimethod that supports args (no kwargs by design).

    Use with the ``@multimethod`` decorator to register type-specific implementations.

    .. note::
        Algorithm from http://www.artima.com/weblogs/viewpost.jsp?thread=101605
    """

    def __init__(self, name):
        self.name = name
        self.typemap = {}

    def __call__(self, *args):
        types = tuple(arg.__class__ for arg in args)
        function = self.typemap.get(types)
        if function is None:
            raise TypeError('no match')
        return function(*args)

    def register(self, types, function):
        if types in self.typemap:
            raise TypeError('duplicate registration')
        self.typemap[types] = function


def multimethod(*types):
    """Decorator for type-based method dispatch (multiple dispatch).

    Register function overloads that dispatch based on argument types.

    :param types: Type(s) to match for this overload.
    :returns: Decorator that registers the function with MultiMethod.

    Example::

        >>> @multimethod(int, int)
        ... def foo(a, b):
        ...     return a + b
        >>> @multimethod(str, str)
        ... def foo(a, b):
        ...     return a + ' ' + b
    """
    def register(function):
        name = function.__name__
        mm = registry.get(name)
        if mm is None:
            mm = registry[name] = MultiMethod(name)
        mm.register(types, function)
        return mm

    return register


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
