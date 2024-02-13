import ast
import base64
import difflib
import inspect
import itertools
import json
import logging
import math
import operator
import os
import re
import signal
import sys
import warnings
from collections.abc import Mapping
from contextlib import contextmanager
from functools import cmp_to_key, reduce, wraps

from libb import collapse, isiterable

logger = logging.getLogger(__name__)

# {{{ Class and Function Manipulations


def attrs(*attrnames):
    """Lazily stuff in get/setters

    >>> class Foo:
    ...     _a = 1
    ...     _b = 2
    ...     _c = 3
    ...     attrs('a', 'b', 'c')
    ...     _z = (_a, _b, _c,)
    ...     z = property(lambda x: x._z)

    vanilla attrs work fine
    >>> f = Foo()
    >>> f.a
    1
    >>> f.a+f.b==f.c
    True

    beware of link between cls._a and self._a
    >>> f.a = 2
    >>> f.a
    2
    >>> f._a
    1

    we can also do lazy definitions like our `z`
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


@contextmanager
def replacekey(d, key, newval):
    """Handy bugger for temporarily patching a dict

    >>> f = dict(x=13)
    >>> with replacekey(f, 'x', 'pho'):
    ...     f['x']
    'pho'
    >>> f['x']
    13

    if the dict does not have the key set before, we return to that state
    >>> rand_key = str(int.from_bytes(os.urandom(10), sys.byteorder))
    >>> with replacekey(os.environ, rand_key, '22'):
    ...     os.environ[rand_key]=='22'
    True
    >>> rand_key in os.environ
    False
    """
    wasset = key in d
    oldval = d.get(key)
    d[key] = newval
    yield
    if wasset:
        d[key] = oldval
    else:
        del d[key]


@contextmanager
def replaceattr(obj, attrname, newval):
    """Handy bugger for temporarily monkey patching an object

    >>> class Foo: pass
    >>> f = Foo()
    >>> f.x = 13
    >>> with replaceattr(f, 'x', 'pho'):
    ...     f.x
    'pho'
    >>> f.x
    13

    if the obj did not have the attr set, we remove it
    >>> with replaceattr(f, 'y', 'boo'):
    ...     f.y=='boo'
    True
    >>> hasattr(f, 'y')
    False
    """
    wasset = hasattr(obj, attrname)
    oldval = getattr(obj, attrname, None)
    setattr(obj, attrname, newval)
    yield
    if wasset:
        setattr(obj, attrname, oldval)
    else:
        delattr(obj, attrname)


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


def include(source, names=()):
    """Include greedy classproperty dict in declaration

    >>> d = dict(x=10, y='foo')
    >>> class Foo:
    ...     include(d)

    >>> Foo.x
    10
    >>> Foo.y
    'foo'
    >>> class Boo:
    ...     include(d, ('y',))

    >>> hasattr(Boo, 'x')
    False
    >>> hasattr(Boo, 'y')
    True
    """
    sys._getframe(1).f_locals.update({name: source[name] for name in names} if names else source)


def singleton(cls):
    """Elegant singleton enforcement via python decorators wiki

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
    >>> f = F()
    >>> f.x == F().x == f.x == 100
    True
    >>> F.x = 50
    >>> f.x == F().x == F.x == 50
    True

    >>> import copy
    >>> fc = copy.deepcopy(f)
    >>> FC = copy.deepcopy(F)
    >>> fc.y==f.y==F.y==FC.y=='y'
    True
    """
    obj = cls()
    # dunders are looked up on the type (class), not instance
    obj.__class__ = type(obj.__class__.__name__, (obj.__class__,), {})
    obj.__class__.__call__ = lambda x: x
    return obj


def memoize(obj):
    """Keep dict of function calls as a function attribute
    re: http://stackoverflow.com/a/3243694/424380
    re: https://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    NOTE: we also have one from web.py which is nice ...

    unique n-length arrays of ints whose abs val sums to k:
    V(n,0)=1; V(0,k)=0; V(n,k) = V(n-1,k) + V(n,k-1) + V(n-1,k-1);

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

    >>> n_with_sum_k_mz = memoize(n_with_sum_k)
    >>> n_with_sum_k_mz(3, 5)
    61
    >>> n_with_sum_k_mz.cache
    {'(3, 5){}': 61}
    """

    cache = obj.cache = {}

    @wraps(obj)
    def memoizer(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = obj(*args, **kwargs)
        return cache[key]

    return memoizer


class classproperty(property):
    """Decorator like @property for classes instead of instances

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
    >>> Foo.a = 2
    >>> Foo.c
    4
    """

    def __get__(desc, self, cls):
        return desc.fget(cls)


def delegate(deleg, attrs):
    """Delegate methods to other objects attached to your object

    >>> class X:
    ...     a = 1

    >>> class Y:
    ...     x = X()
    ...     delegate('x', 'a')

    >>> Y().a
    1

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
    for attr in attrs:
        caller_locals[attr] = _makeprop(attr)


def lazy_property(fn):
    """Decorator that makes a property lazy-evaluated.

    >>> import time
    >>> class Sloth(object):
    ...     def _slow_cool(self, n):
    ...         time.sleep(n)
    ...         return n**2
    ...     @lazy_property
    ...     def slow(self):
    ...         return True
    ...     @lazy_property
    ...     def cool(self):
    ...         return self._slow_cool(3)
    >>> x = time.time()
    >>> s = Sloth()
    >>> time.time()-x < 1
    True
    >>> time.time()-x < 1
    True
    >>> hasattr(s, '_lazy_slow')
    False
    >>> s.slow
    True
    >>> hasattr(s, '_lazy_slow')
    True
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

    return _lazy_property


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

# }}}
#
# list like methods from different work
#


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
    else:
        return default


def choose(n, k):
    """Simple implementation of n choose k

    >>> choose(10, 3)
    120
    """
    return int(round(reduce(operator.mul, (float(n - i) / (i + 1) for i in range(k)), 1)))


def base64file(fil):
    return base64.encodestring(open(fil, 'rb').read())


# {{{ Dictionary


def ismapping(something):
    """Does this look kinda sorta like a dict?

    >>> ismapping(dict())
    True
    """
    return isinstance(something, Mapping)


def flatten(kv, prefix=None):
    """Flatten list of dictionaries, recursively flattening nested ones

    >>> data = [
    ...     {'event': 'User Clicked', 'properties': {'user_id': '123', 'page_visited': 'contact_us'}},
    ...     {'event': 'User Clicked', 'properties': {'user_id': '456', 'page_visited': 'homepage'}},
    ...     {'event': 'User Clicked', 'properties': {'user_id': '789', 'page_visited': 'restaurant'}}
    ... ]

    >>> from pandas import DataFrame
    >>> df = DataFrame({k:v for k,v in flatten(kv)} for kv in data)
    >>> list(df)
    ['event', 'properties_user_id', 'properties_page_visited']
    >>> len(df)
    3
    """
    if prefix is None:
        prefix = []
    for k, v in list(kv.items()):
        if isinstance(v, dict):
            yield from flatten(v, prefix + [str(k)])
        else:
            if prefix:
                yield '_'.join(prefix + [str(k)]), v
            else:
                yield str(k), v


def cmp(left, right):
    """Python 2 cmp function.
    - Handle null values gracefully in sort comparisons

    >>> cmp(None, 2)
    -1
    >>> cmp(2, None)
    1
    >>> cmp(-1, 2)
    -1
    >>> cmp(2, -1)
    1
    >>> cmp(1, 1)
    0
    """
    _cmp = lambda a, b: (a > b) - (a < b)
    try:
        _ = all(left) and all(right)  # check if iterable
        if None in left and None in right:
            return 0
        elif None in left and None not in right:
            return -1
        elif None not in left and None in right:
            return 1
        return _cmp(left, right)
    except TypeError:
        pass

    if left is None and right is None:
        return 0
    elif left is None and right is not None:
        return -1
    elif left is not None and right is None:
        return 1
    return _cmp(left, right)


def multikeysort(items, columns, _cmp=cmp, inplace=False):
    """Sort list of dictionaries by list of keys
    https://stackoverflow.com/a/1144405

    equivalent to sql `sort by` order, map no sign to asc, - to desc
    >>> ds = [
    ...     {'category': 'c1', 'total': 96.0},
    ...     {'category': 'c2', 'total': 96.0},
    ...     {'category': 'c3', 'total': 80.0},
    ...     {'category': 'c4', 'total': None},
    ...     {'category': 'c5', 'total': 80.0},
    ... ]

    >>> asc = multikeysort(ds, ['total', 'category'])
    >>> total = [_['total'] for _ in asc]
    >>> assert all([cmp(total[i], total[i+1]) in (0,-1,) for i in range(len(total)-1)])

    >>> us = multikeysort(ds, ['missing',])
    >>> assert us[0]['total'] == 96.0
    >>> assert us[1]['total'] == 96.0
    >>> assert us[2]['total'] == 80.0
    >>> assert us[3]['total'] == None
    >>> assert us[4]['total'] == 80.0

    >>> us = multikeysort(ds, None)
    >>> assert us[0]['total'] == 96.0
    >>> assert us[1]['total'] == 96.0
    >>> assert us[2]['total'] == 80.0
    >>> assert us[3]['total'] == None
    >>> assert us[4]['total'] == 80.0

    >>> multikeysort(ds, ['-total', 'category'], inplace=True) # desc
    >>> total = [_['total'] for _ in ds]
    >>> assert all([cmp(total[i], total[i+1]) in (0, 1,) for i in range(len(total)-1)])
    """
    if not isinstance(columns, (list, tuple)):
        columns = (columns,)

    m = re.compile(r'^-')
    known = set(collapse(*[list(d.keys()) for d in items]))
    columns = [x for x in columns if x and m.sub('', x) in known]

    i = operator.itemgetter
    comparers = [(i(m.sub('', col)), -1) if m.match(col) else (i(col), 1) for col in columns]

    def comparer(left, right):
        comparer_iter = [_cmp(fn(left), fn(right)) * mult for fn, mult in comparers]
        return next((result for result in comparer_iter if result), 0)

    if not inplace:
        return sorted(items, key=cmp_to_key(comparer))

    items.sort(key=cmp_to_key(comparer))


def map(func, *iterables):
    """Simulate a Python2-like map, which continues until the longest of the
    argument iterables is exhausted, extending the other arguments with None

    >>> def foo(a, b):
    ...     if b is not None:
    ...         return a - b
    ...     return -a
    >>> list(map(foo, range(5), [3,2,1]))
    [-3, -1, 1, -3, -4]
    """
    zipped = itertools.zip_longest(*iterables)
    if func is None:
        return zipped
    return itertools.starmap(func, zipped)


def get_attrs(klazz):
    """Get class attributes

    >>> class MyClass(object):
    ...     a = '12'
    ...     b = '34'
    ...     def myfunc(self):
    ...         return self.a
    >>> get_attrs(MyClass)
    [('a', '12'), ('b', '34')]
    """
    attrs = inspect.getmembers(klazz, lambda a: not (inspect.isroutine(a)))
    return [a for a in attrs if not (a[0].startswith('__') and a[0].endswith('__'))]

# }}}


def suppresswarning(func):
    """Suppressing numpy (or other) runtime warnings"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=RuntimeWarning)
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
        else:
            if latest is None:
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
            else:
                if latest.get(k) is None:
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


def ismapping(something):
    """Does this look kinda sorta like a dict?

    >>> ismapping(dict())
    True
    """
    return isinstance(something, Mapping)


def merge_dict(old, new, inplace=True):
    """Key for key merge of two dictionaries

    non-inplace modify
    >>> l1 = {'a': {'b': 1, 'c': 2}, 'b': 2}
    >>> l2 = {'a': {'a': 9}, 'c': 3}
    >>> merge_dict(l1, l2, inplace=False)
    {'a': {'b': 1, 'c': 2, 'a': 9}, 'b': 2, 'c': 3}
    >>> l1=={'a': {'b': 1, 'c': 2}, 'b': 2}
    True
    >>> l2=={'a': {'a': 9}, 'c': 3}
    True

    multilevel merging
    >>> xx = {'a': {'b': 1, 'c': 2}, 'b': 2}
    >>> nice = {'a': {'a': 9}, 'c': 3}

    >>> merge_dict(xx, nice)
    >>> 'a' in xx['a']
    True
    >>> 'c' in xx
    True

    warning, it will overwrite stuff
    >>> warn = {'a': {'c': 9}, 'b': 3}
    >>> merge_dict(xx, warn)
    >>> xx['a']['c']
    9
    >>> xx['b']
    3

    tries to be smart with iterables, but does *not* force types
    >>> l1 = {'a': {'c': [5, 2]}, 'b': 1}
    >>> l2 = {'a': {'c': [1, 2]}, 'b': 3}
    >>> l3 = {'a': {'c': (1, 2,)}, 'b': 3}
    >>> merge_dict(l1, l2)
    >>> len(l1['a']['c'])
    4
    >>> l1['b']
    3
    >>> merge_dict(l1, l3)
    Traceback (most recent call last):
        ...
    TypeError: can only concatenate list (not "tuple") to list
    """
    if not inplace:
        # thread-safe solution
        old = json.loads(json.dumps(old))
    for key, new_val in new.items():
        old_val = old.get(key)
        if ismapping(old_val) and ismapping(new_val):
            merge_dict(old_val, new_val, inplace=True)
        elif isiterable(old_val) and isiterable(new_val):
            old[key] = old_val + new_val
        else:
            old[key] = new_val
    if not inplace:
        return old


def fuzzy_search(search_term, items):
    """Search for term in a list of items with one or more terms
    Scores each lower-cased "word" (split by space, -, and _) separately
    Returns the highest score **very** brute force, FIXME improve it

    >>> results = fuzzy_search("OCR",
    ...     [("Omnicare", "OCR",), ("Ocra", "OKK"), ("GGG",)])
    >>> (_,ocr_score), (_,okk_score), (_,ggg_score) = results
    >>> ocr_score
    1.0
    >>> okk_score  # doctest: +ELLIPSIS
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


#
# db-api utilities
#


def chunked(cursor, size=1000):
    while True:
        this_chunk = cursor.fetchmany(size)
        if not this_chunk:
            break
        yield from this_chunk


# {{{ Geography, Mercator Projections

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

# }}}


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

    >>> help(B.myfunction) # doctest: +NORMALIZE_WHITESPACE
    Help on function myfunction in module __main__:
    <BLANKLINE>
    myfunction()
        Documentation for A.
        Extra details for B.
    <BLANKLINE>
    >>> help(C.myfunction) # doctest: +NORMALIZE_WHITESPACE
    Help on function myfunction in module __main__:
    <BLANKLINE>
    myfunction()
        Extra details for B.
        Documentation for A.
    <BLANKLINE>
    >>> help(E.myfunction) # doctest: +NORMALIZE_WHITESPACE
    Help on function myfunction in module __main__:
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


def extend_instance(obj, cls, left=True):
    """Apply mixins/extend base class after creation

    TODO: add better tests. ABC changes order precedence L-R.

    >>> from pprint import pprint
    >>> class X:pass
    >>> class Y: pass
    >>> class Z:pass
    >>> class A(X,Y):pass
    >>> class B(A,Y,Z):pass
    >>> class F(B): pass
    >>> pprint(F.mro())
    [<class '__main__.F'>,
     <class '__main__.B'>,
     <class '__main__.A'>,
     <class '__main__.X'>,
     <class '__main__.Y'>,
     <class '__main__.Z'>,
     <class 'object'>]
    >>> class F_L:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=True)
    >>> class F_R:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=False)
    >>> f_l = F_L()
    >>> pprint(f_l.__class__.__mro__)
    (<class '__main__.F_L'>,
     <class '__main__.B'>,
     <class '__main__.A'>,
     <class '__main__.X'>,
     <class '__main__.Y'>,
     <class '__main__.Z'>,
     <class '__main__.F_L'>,
     <class 'object'>)
    >>> f_r = F_R()
    >>> pprint(f_r.__class__.__mro__)
    (<class '__main__.F_R'>,
     <class '__main__.F_R'>,
     <class '__main__.B'>,
     <class '__main__.A'>,
     <class '__main__.X'>,
     <class '__main__.Y'>,
     <class '__main__.Z'>,
     <class 'object'>)
    """
    if left:
        obj.__class__ = type(obj.__class__.__name__, (cls, obj.__class__), {})
    else:
        obj.__class__ = type(obj.__class__.__name__, (obj.__class__, cls), {})


def add_branch(tree, vector, value):
    """
    Given a dict, a vector, and a value, insert the value into the dict
    at the tree leaf specified by the vector.  Recursive!

    Params:
        data (dict): The data structure to insert the vector into.
        vector (list): A list of values representing the path to the leaf node.
        value (object): The object to be inserted at the leaf

    Returns
        dict: The dict with the value placed at the path specified.

    Algorithm:
        If we're at the leaf, add it as key/value to the tree
        Else: If the subtree doesn't exist, create it.
              Recurse with the subtree and the left shifted vector.
        Return the tree.

    from https://stackoverflow.com/a/47276490

    For example for parsing ini files with dot-delimited keys in different
    sections:

    [app]
    site1.ftp.host = hostname
    site1.ftp.username = username
    site1.database.hostname = db_host
    ; etc..

    >>> tree = {'a': 'apple'}

    Example 1:
    >>> vector = ['b', 'c', 'd']
    >>> value = 'dog'
    >>> tree = add_branch(tree, vector, value)
    >>> tree
    {'a': 'apple', 'b': {'c': {'d': 'dog'}}}

    Example 2:
    >>> vector2 = ['b', 'c', 'e']
    >>> value2 = 'egg'
    >>> tree = add_branch(tree, vector2, value2)
    >>> tree
    {'a': 'apple', 'b': {'c': {'d': 'dog', 'e': 'egg'}}}

    """
    key = vector[0]
    tree[key] = value \
        if len(vector) == 1 \
        else add_branch(tree.get(key, {}),
                        vector[1:],
                        value)
    return tree


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


if __name__ == '__main__':
    __import__('doctest').testmod()
