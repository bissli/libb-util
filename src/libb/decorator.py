import ast
import inspect
import logging

logger = logging.getLogger(__name__)


def find_decorators(target):
    """https://stackoverflow.com/a/9580006"""
    res = {}

    def visit_function_def(node):
        res[node.name] = [ast.dump(e) for e in node.decorator_list]

    V = ast.NodeVisitor()
    V.visit_FunctionDef = visit_function_def
    V.visit(compile(inspect.getsource(target), '?', 'exec', ast.PyCF_ONLY_AST))
    return res


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
