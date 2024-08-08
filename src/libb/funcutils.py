import ast
import inspect
import logging
import sys
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
    ]


def is_instance_method(func):
    return len(func.__qualname__.split('.')) > 1


def find_decorators(target):
    """https://stackoverflow.com/a/9580006"""
    res = {}

    def visit_function_def(node):
        res[node.name] = [ast.dump(e) for e in node.decorator_list]

    V = ast.NodeVisitor()
    V.visit_FunctionDef = visit_function_def
    V.visit(compile(inspect.getsource(target), '?', 'exec', ast.PyCF_ONLY_AST))
    return res


def compose(*functions):
    """Return a function folding over a list of functions
    each arg must have a single param, so that it is explicit

    >>> f = lambda x: x+4
    >>> g = lambda y: y/2
    >>> h = lambda z: z*3
    >>> fgh = compose(f, g, h)

    beware of order for non-commutative functions (first in, **last** out)
    >>> fgh(2)==h(g(f(2)))
    False
    >>> fgh(2)==f(g(h(2)))
    True
    """
    return reduce(lambda f, g: lambda x: f(g(x)), functions)


def composable(decorators):
    """Decorator that takes a list of decorators to be composed

    useful when list of decorators starts getting large and unruly

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

    Despite the similar name, composed decorators are not
    interchangeable with `compose` for standard functions,
    since decorators return functions, not the func output
    >>> func = compose(m3, d2, p3)(4)
    >>> hasattr(func, '__call__')
    True
    >>> compose(lambda n: n*3., lambda n: n/2., p3)(4)
    10.5

    what they do allow is consolidating longer decorator chains
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
    """Decorator: Copy the docstring of `fromfunc`

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

    do not activate doctests!
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
        docstr_disabled = ''
        for line in docstr.splitlines():
            docstr_disabled += line
            if '>>>' in line:
                docstr_disabled += ' # doctest: +DISABLE'
        return docstr_disabled

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
    """Finds the calling function in many decent cases."""
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
    """Repeat function x_times

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
    @wraps(func)
    def wrap(*args, **kw):
        ts = time()
        result = func(*args, **kw)
        te = time()
        logger.debug(f'func:{func.__name__!r} args:[{args!r}, {kw!r}] took: {te-ts:2.4f} sec')
        return result
    return wrap


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
