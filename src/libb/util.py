"""Main utilities module"""

# Imports ................................................................ {{{1

import base64
import difflib
import logging
import math
import operator
import os
import re
import signal
import sys
import warnings
from collections.abc import Iterable, MutableSet
from contextlib import contextmanager
from functools import reduce, wraps

logger = logging.getLogger(__name__)

#  ....................................................................... }}}1
# Collections (Non-Dict) ................................................. {{{1


class OrderedSet(MutableSet):
    """From Raymond Hettinger on ActiveState
    https://code.activestate.com/recipes/576694/

    >>> s = OrderedSet('abracadaba')
    >>> t = OrderedSet('simsalabim')
    >>> (s | t)
    OrderedSet(['a', 'b', 'r', 'c', 'd', 's', 'i', 'm', 'l'])
    >>> (s & t)
    OrderedSet(['a', 'b'])
    >>> (s - t)
    OrderedSet(['r', 'c', 'd'])
    """

    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

# ........................................................................ }}}1
# Timeout ..................................................... {{{1


class timeout:
    """with statement to manage timeouts for potential hanging code
    http://stackoverflow.com/a/22348885/424380

    >>> import time
    >>> with timeout(1):
    ...     time.sleep(2)
    ...     print("foo")
    Traceback (most recent call last):
        ...
    OSError: Timeout!!
    >>> with timeout(1):
    ...     print("foo")
    foo
    """

    def __init__(self, seconds=100, error_message='Timeout!!'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise OSError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)

#  ....................................................................... }}}1
# Functools .............................................................. {{{1


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

#  ....................................................................... }}}1
# List ................................................................... {{{1


def same_order(ref, comp):
    """Compare two lists and assert that the elements in the reference list
    appear in the same order in the comp list, regardless of comp list size

    >>> r = ['x', 'y', 'z']
    >>> c = ['x', 'a', 'b', 'c', 'y', 'd', 'e', 'f', 'z', 'h']
    >>> same_order(r, c)
    True

    >>> c = ['x', 'a', 'b', 'c', 'z', 'd', 'e', 'f', 'y', 'h']
    >>> same_order(r, c)
    False
    """
    if len(comp) < len(ref):
        return False
    order = []
    for r in ref:
        try:
            order.append(comp.index(r))
        except ValueError:
            return False
    return sorted(order) == order


def invert(dct):
    return {v: k for k, v in list(dct.items())}


def mapkeys(func, dct):
    return {func(key): val for key, val in list(dct.items())}


def mapvals(func, dct):
    return {key: func(val) for key, val in list(dct.items())}


def coalesce(*args):
    return next((a for a in args if a is not None), None)


def getitem(sequence, index, default=None):
    if index < len(sequence):
        return sequence[index]
    return default


def choose(n, k):
    """Simple implementation of n choose k

    >>> choose(10, 3)
    120
    """
    return int(round(reduce(operator.mul, (float(n - i) / (i + 1) for i in range(k)), 1)))


def base64file(fil):
    return base64.encodestring(open(fil, 'rb').read())

#  ....................................................................... }}}1
# {{{ Unsorted


def suppresswarning(func):
    """Suppressing warnings
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            return func(*args, **kwargs)
    return wrapper


def is_numeric(txt):
    """Call something a number if we can force it into a float
    WARNING: complex types cannot be converted to float

    >>> is_numeric('a')
    False
    >>> is_numeric(1e4)
    True
    >>> is_numeric('1E2')
    True
    >>> is_numeric(complex(-1,0))
    False
    """
    try:
        float(txt)
        return True
    except (ValueError, TypeError):
        return False


registry = {}


class MultiMethod:
    """Multimethod that supports args no kwargs (by design ...)
    via bdfl http://www.artima.com/weblogs/viewpost.jsp?thread=101605

    @multimethod(int, int)
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
    def register(function):
        name = function.__name__
        mm = registry.get(name)
        if mm is None:
            mm = registry[name] = MultiMethod(name)
        mm.register(types, function)
        return mm

    return register


def peel(str_or_iter):
    """Peel iterator one by one, yield item, aliasor item, item

    >>> list(peel(["a", ("", "b"), "c"]))
    [('a', 'a'), ('', 'b'), ('c', 'c')]
    """
    things = (_ for _ in str_or_iter)
    while things:
        try:
            this = next(things)
        except StopIteration:
            return
        if isinstance(this, (tuple, list)):
            yield this
        else:
            yield this, this


def rpeel(str_or_iter):
    """Peel iterator one by one, yield alias if tuple, else item"

    >>> list(rpeel(["a", ("", "b"), "c"]))
    ['a', 'b', 'c']
    """
    things = (_ for _ in str_or_iter)
    while things:
        try:
            this = next(things)
        except StopIteration:
            return
        if isinstance(this, (tuple, list)):
            yield this[-1]
        else:
            yield this


def backfill(values):
    """Back-fill a sorted array with the latest value

    >>> backfill([None, None, 1, 2, 3, None, 4])
    [1, 1, 1, 2, 3, 3, 4]
    >>> backfill([1,2,3])
    [1, 2, 3]
    >>> backfill([None, None, None])
    [None, None, None]
    >>> backfill([])
    []
    >>> backfill([1, 2, 3, None])
    [1, 2, 3, 3]
    """
    latest = None
    missing = 0  # at start
    filled = []
    for val in values:
        if val is not None:
            latest = val
            if missing:
                filled = [latest] * missing
                missing = 0
            filled.append(val)
        elif latest is None:
            missing += 1
        else:
            filled.append(latest)
    return filled or values


def backfill_iterdict(iterdict):
    """Back-fill a sorted iterdict with the latest value

    >>> backfill_iterdict([
    ...     {'a': 1, 'b': None},
    ...     {'a': 4, 'b': 2},
    ...     {'a': None, 'b': None},
    ...     {'a': 3, 'b': None}])
    [{'a': 1, 'b': 2}, {'a': 4, 'b': 2}, {'a': 4, 'b': 2}, {'a': 3, 'b': 2}]
    >>> backfill_iterdict([])
    []
    >>> backfill_iterdict([
    ...     {'a': 9, 'b': 2},
    ...     {'a': 4, 'b': 1},
    ...     {'a': 3, 'b': 4},
    ...     {'a': 3, 'b': 3}])
    [{'a': 9, 'b': 2}, {'a': 4, 'b': 1}, {'a': 3, 'b': 4}, {'a': 3, 'b': 3}]
    """
    latest = {}
    missing = {}  # front-fill w first value
    filled = []
    for _dict in iterdict:
        this = {}
        for k, v in list(_dict.items()):
            if v is not None:
                latest[k] = v
                if k in missing:
                    for j in range(missing[k]):
                        filled[j][k] = latest[k]
                this[k] = v
            elif latest.get(k) is None:
                missing[k] = (missing.get(k) or 0) + 1
            else:
                this[k] = latest[k]
        filled.append(this)
    return filled


def align_iterdict(iterdict_a, iterdict_b, **kw):
    """Given two lists of dicts ('iterdicts'), sorted on some attribute,
    build a single list with dicts, with keys within a given tolerance
    anything that cannot be aligned is DROPPED

    >>> list(zip(*align_iterdict(
    ...	[{'a': 1}, {'a': 2}, {'a': 5}],
    ...	[{'b': 5}],
    ...	a='a',
    ...	b='b',
    ...	diff=lambda x, y: x - y,
    ...	)))
    [({'a': 5},), ({'b': 5},)]

    >>> list(zip(*align_iterdict(
    ...	[{'b': 5}],
    ...	[{'a': 1}, {'a': 2}, {'a': 5}],
    ...	a='b',
    ...	b='a',
    ...	diff=lambda x, y: x - y
    ...	)))
    [({'b': 5},), ({'a': 5},)]
    """
    attr_a = kw.get('a', 'date')
    attr_b = kw.get('b', 'date')
    tolerance = kw.get('tolerance', 0)
    diff = kw.get('diff', lambda x, y: (x - y).days)

    gen_a, gen_b = (_ for _ in iterdict_a), (_ for _ in iterdict_b)
    this_a, this_b = None, None
    while gen_a or gen_b:
        if not this_a or diff(this_a.get(attr_a), this_b.get(attr_b)) < tolerance:
            try:
                this_a = next(gen_a)
            except StopIteration:
                break
            logger.debug(f'Advanced A to {this_a.get(attr_a)}')
        if not this_b or diff(this_a.get(attr_a), this_b.get(attr_b)) > tolerance:
            try:
                this_b = next(gen_b)
            except StopIteration:
                break
            logger.debug(f'Advanced B to {this_b.get(attr_b)}')
        if abs(diff(this_a.get(attr_a), this_b.get(attr_b))) <= tolerance:
            logger.debug('Aligned iters to A {} B {}'.format(this_a.get(attr_a), this_b.get(attr_b)))
            yield this_a, this_b
            try:
                this_a, this_b = next(gen_a), next(gen_b)
            except StopIteration:
                break


def scriptname(task=None):
    """Return name of script being run, without the file extension

    >>> scriptname(__file__)
    'util'
    >>> scriptname() in sys.argv[0]
    True
    >>> scriptname()==sys.argv[0]
    False
    """
    task = task or sys.argv[0]
    if task:
        app, _ = os.path.splitext(os.path.basename(task))
    else:
        app = ''
    return app


def fuzzy_search(search_term, items):
    """Search for term in a list of items with one or more terms
    Scores each lower-cased "word" (split by space, -, and _) separately
    Returns the highest score **very** brute force, FIXME improve it

    >>> results = fuzzy_search("OCR",
    ...     [("Omnicare", "OCR",), ("Ocra", "OKK"), ("GGG",)])
    >>> (_,ocr_score), (_,okk_score), (_,ggg_score) = results
    >>> ocr_score
    1.0
    >>> okk_score
    0.85...
    >>> ggg_score
    0.0
    >>> list(zip(*fuzzy_search("Ramco-Gers",
    ...     [("RAMCO-GERSHENSON PROPERTIES", "RPT US Equity",),
    ...      ("Ramco Inc.", "RMM123FAKE")])))[1]
    (1.0, 1.0)
    """
    score_words = lambda a, b: difflib.SequenceMatcher(a=a, b=b).ratio() if a and b else 0.0
    lower_split = lambda x: re.split(r'[\s\-_]', x.lower())
    for item in items:
        _max = max(
            score_words(word, search_word)
            for term in item
            for word in lower_split(term)
            for search_word in lower_split(search_term)
        )
        yield item, _max


# Geography, Mercator Projections ........................................ {{{1


def merc_x(lon, r_major=6378137.0):
    """Project longitude into mercator / radians from major axis

    >>> "{:0.3f}".format(merc_x(40.7484))
    '4536091.139'
    """
    return r_major * math.radians(lon)


def merc_y(lat, r_major=6378137.0, r_minor=6356752.3142):
    """Project latitude into mercator / radians from major/minor axes

    >>> "{:0.3f}".format(merc_y(73.9857))
    '12468646.871'
    """
    if lat > 89.5:
        lat = 89.5
    if lat < -89.5:
        lat = -89.5
    eccent = math.sqrt(1 - (r_minor / r_major) ** 2)
    phi = math.radians(lat)
    sinphi = math.sin(phi)
    con = eccent * sinphi
    com = eccent / 2
    den = ((1.0 - con) / (1.0 + con)) ** com
    ts = math.tan((math.pi / 2 - phi) / 2) / den
    y = 0.0 - r_major * math.log(ts)
    return y

#  ....................................................................... }}}1
# {{{ Unsorted


def format_phone(phone):
    """Reformat phone numbers for display

    >>> format_phone('6877995559')
    '687-799-5559'
    """
    pstr = str(phone)
    parr = [pstr[-10:-7], pstr[-7:-4], pstr[-4:]]
    if len(pstr) > 10:
        parr.insert(0, pstr[:-10])
    formatted_phone = '-'.join(parr)
    return formatted_phone


def kryptophy(blah):
    """Intentionally mysterious"""
    return int('0x' + ''.join([hex(ord(x))[2:] for x in blah]), 16)


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


@contextmanager
def suppress_print():
    """Suppress `print` in case someone decided to include
    """
    try:
        _original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        yield
    finally:
        sys.stdout.close()
        sys.stdout = _original_stdout


def wrap_suppress_print(func):
    """Decoractor for `suppress print`
    """
    @wraps(func)
    def wrapped(*a, **kw):
        with suppress_print():
            return func(*a, **kw)
    return wrapped

# }}}


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)

# vim: foldenable
