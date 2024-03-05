"""Main utilities module"""

# {{{ Imports

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
from abc import ABCMeta
from collections import defaultdict
from collections.abc import Iterable, Mapping, MutableMapping, MutableSet
from contextlib import contextmanager, suppress
from functools import cmp_to_key, reduce, wraps
from typing import Dict, Iterable, List

import more_itertools
import psutil
import regex as re
from trace_dkey import trace

logger = logging.getLogger(__name__)

# }}}
# {{{ Itertools


def isiterable(arg):
    """Check for iterable type (but not String)"""
    return isinstance(arg, Iterable) and not isinstance(arg, str)


def divide(iterable, size):
    """Split an iterable into sub-iterables of length `size`

    >>> list(divide(list(range(10)), 5))
    [(0, 1, 2, 3, 4), (5, 6, 7, 8, 9)]
    """
    iterable = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(iterable, size))
        if chunk:
            yield chunk
        if len(chunk) < size:
            break


def collapse(*args):
    """Recursive flatten of list of lists, returns a generator in original order
    equivalent effect to more_itertools.collapse

    >>> l1 = ['a', ['b', ('c', 'd')]]
    >>> l2 = [0, 1, (2, 3), [[4, 5, (6, 7, (8,), [9]), 10]], (11,)]
    >>> list(collapse([l1, -2, -1, l2]))
    ['a', 'b', 'c', 'd', -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    """
    return (e for a in args for e in (collapse(*a) if isinstance(a, (tuple, list)) else (a,)))


def groupby(iterable, keyfunc):
    """TODO: add tests!"""
    groups = defaultdict(list)
    for item in iterable:
        groups[keyfunc(item)].append(item)
    return groups


def compact(iterable):
    """Get the none junk out of an iterable -- also removes zero!!

    >>> compact([0,2,3,4,None,5])
    (2, 3, 4, 5)
    """
    return tuple(item for item in iterable if item)


def hashby(iterable, keyfunc):
    return {keyfunc(item): item for item in iterable}


def negate_permute(*items):
    """For each item in iterable items,
    rebuild tuple with just the one item negated,
    get all permutations of tuple with negated item
    ~= permutation of each + and - version of each item

    >>> next(negate_permute(1, 2))
    (-1, 1, -2, 2)
    >>> next(negate_permute(-float('inf'), 0))
    (inf, -inf, 0, 0)
    """
    yield from itertools.permutations(itertools.chain(*((-a, a) for a in items)))


def partition(pred, iterable):
    """Partition an iterable by False/True of function `pred`

    >>> falses, trues = partition(lambda x: x==1, [1, 2, 3, 1, 2, 3])
    >>> list(falses)
    [2, 3, 2, 3]
    >>> list(trues)
    [1, 1]

    >>> somedict = dict(a=1, b=2, c=3)
    >>> falses, trues = partition(lambda kv: kv[0] in ('a','b'), list(somedict.items()))
    >>> list(falses)
    [('c', 3)]
    >>> list(trues)
    [('a', 1), ('b', 2)]

    >>> somegen = (_ for _ in range(10))
    >>> odd, even = partition(lambda x: x % 2 == 0, somegen)
    >>> list(odd)
    [1, 3, 5, 7, 9]
    >>> list(even)
    [0, 2, 4, 6, 8]
    """
    return more_itertools.partition(pred, iterable)


def roundrobin(*iterables):
    """Pluck one at a time from an arbitrary number of iterables
    - Recipe credited to George Sakkis

    >>> " ".join(roundrobin('ABC', 'D', 'EF'))
    'A D E B F C'
    """
    return more_itertools.roundrobin(*iterables)


def grouper(n, iterable, fillvalue=None):
    """Group list into list of sublists

    >>> [''.join(_) for _ in grouper(3, 'ABCDEFG', 'x')]
    ['ABC', 'DEF', 'Gxx']
    """
    return more_itertools.grouper(iterable, n, incomplete='fill', fillvalue=fillvalue)


def infinite_iterator(iterable):
    """Exactly what it says

    >>> ii = infinite_iterator([1,2,3,4,5])
    >>> [next(ii) for i in range(9)]
    [1, 2, 3, 4, 5, 1, 2, 3, 4]
    """
    global i
    i = 0

    def next():
        global i
        while True:
            n = iterable[i % len(iterable)]
            i += 1
            yield n

    return next()

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
# Collections (Dict) ..................................................... {{{1


class attrdict(dict):
    """The vanilla attrdict everyone has in their utils

    >>> import copy
    >>> d = attrdict(x=10, y='foo')
    >>> d.x
    10
    >>> d['x']
    10
    >>> d.y = 'baa'
    >>> d['y']
    'baa'
    >>> g = d.copy()
    >>> g.x = 11
    >>> d.x
    10
    >>> d.z = 1
    >>> d.z
    1
    >>> tricky = [d, g]
    >>> tricky2 = copy.copy(tricky)
    >>> tricky2[1].x
    11
    >>> tricky2[1].x = 12
    >>> tricky[1].x
    12
    >>> righty = copy.deepcopy(tricky)
    >>> righty[1].x
    12
    >>> righty[1].x = 13
    >>> tricky[1].x
    12

    Handles obj.get('attr'), obj['attr'], and obj.attr
    >>> class A(attrdict):
    ...     @property
    ...     def x(self):
    ...         return 1
    >>> a = A()
    >>> a['x'] == a.x == a.get('x')
    True
    >>> a.get('b')
    >>> a['b']
    Traceback (most recent call last):
        ...
    KeyError: 'b'
    >>> a.b
    Traceback (most recent call last):
        ...
    AttributeError: b
    """

    __slots__ = ()

    def __getattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        return self[attrname]

    def __setattr__(self, attrname, attrval):
        if isinstance(attrval, ABCMeta):
            dict.__setattr__(self, attrname, attrval)
        else:
            self[attrname] = attrval

    def __delattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        self.pop(attrname)

    def __getitem__(self, attrname):
        if attrname in self:
            return dict.__getitem__(self, attrname)
        if hasattr(self, attrname):
            return dict.__getattribute__(self, attrname)
        raise KeyError(attrname)

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def update(self, *args, **kwargs):
        dict.update(self, *args, **kwargs)
        return self

    def copy(self, **kwargs):
        newdict = attrdict(dict.copy(self))
        return newdict.update(**kwargs)


class lazydict(attrdict):
    """Attrdict where functions get stored as lazy calculations

    >>> a = lazydict(a=1, b=2, c=lambda x: x.a+x.b)
    >>> a.c
    3
    >>> a.a = 99
    >>> a.c
    101
    >>> a.z = 1
    >>> a.z
    1

    make sure we dont share descriptors, could cause awful bugs
    >>> z = lazydict(a=2, y=4, f=lambda x: x.a*x.y)
    >>> z.b
    Traceback (most recent call last):
        ...
    AttributeError: b
    >>> z.c
    Traceback (most recent call last):
        ...
    AttributeError: c
    >>> z.f
    8

    a's attrs should be unaffected
    >>> a.f
    Traceback (most recent call last):
        ...
    AttributeError: f
    """

    def __getattr__(self, attrname):
        if attrname not in self:
            raise AttributeError(attrname)
        attrval = self[attrname]
        if callable(attrval):
            return attrval(self)
        return attrval


class emptydict(attrdict):
    """Attrdict where non-existing fields return None silently

    >>> a = emptydict(a=1, b=2)
    >>> a.c == None
    True
    """

    def __getattr__(self, attrname):
        if attrname not in self:
            return None
        return self.get(attrname, None)

    def __getitem__(self, attrname):
        return self.__getattr__(attrname)


class bidict(dict):
    """Bidirectional dictionary that allows multiple keys with same value

    >>> bd = bidict({'a': 1, 'b': 2})
    >>> bd
    {'a': 1, 'b': 2}
    >>> bd.inverse
    {1: ['a'], 2: ['b']}

    two keys can have the same value (= 1)
    >>> bd['c'] = 1
    >>> bd
    {'a': 1, 'b': 2, 'c': 1}
    >>> bd.inverse
    {1: ['a', 'c'], 2: ['b']}

    remove a key
    >>> del bd['c']
    >>> bd
    {'a': 1, 'b': 2}
    >>> bd.inverse
    {1: ['a'], 2: ['b']}
    >>> del bd['a']
    >>> bd
    {'b': 2}
    >>> bd.inverse
    {2: ['b']}

    set key to new value
    >>> bd['b'] = 3
    >>> bd
    {'b': 3}
    >>> bd.inverse
    {2: [], 3: ['b']}
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in list(self.items()):
            self.inverse.setdefault(value, []).append(key)

    def __setitem__(self, key, value):
        if key in self:
            self.inverse[self[key]].remove(key)
        super().__setitem__(key, value)
        self.inverse.setdefault(value, []).append(key)

    def __delitem__(self, key):
        self.inverse.setdefault(self[key], []).remove(key)
        if self[key] in self.inverse and not self.inverse[self[key]]:
            del self.inverse[self[key]]
        super().__delitem__(key)


class MutableDict(dict):
    """Extends dictionary to include insert_before and insert_after methods.
    Since python3.7 dictionaries keep insert order.
    """

    def insert_before(self, key, new_key, val):
        """Insert new_key:value into dict before key"""
        keys = list(self.keys())
        vals = list(self.values())

        insert_idx = keys.index(key)

        keys.insert(insert_idx, new_key)
        vals.insert(insert_idx, val)

        self.clear()
        self.update({x: vals[i] for i, x in enumerate(keys)})

    def insert_after(self, key, new_key, val):
        """Insert new_key:value into dict after key"""
        keys = list(self.keys())
        vals = list(self.values())

        insert_idx = keys.index(key) + 1

        if keys[-1] != key:
            keys.insert(insert_idx, new_key)
            vals.insert(insert_idx, val)
            self.clear()
            self.update({x: vals[i] for i, x in enumerate(keys)})
        else:
            self.update({new_key: val})


class CaseInsensitiveDict(MutableMapping):
    """A case-insensitive ``dict``-like object.
    Implements all methods and operations of
    ``MutableMapping`` as well as dict's ``copy``. Also
    provides ``lower_items``.
    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``,
    ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()``
    will contain case-sensitive keys. However, querying and contains
    testing is case insensitive::
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True
    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.
    If the constructor, ``.update``, or equality comparison
    operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    def __init__(self, data=None, **kwargs):
        self._store = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        return dict(self.lower_items()) == dict(other.lower_items())

    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))

# }}}
# Class and Object ..................................................... {{{1


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

#  ....................................................................... }}}1
# Dict ................................................................... {{{1


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


def unnest(d, keys=None):
    """Recursively convert dict into list of tuples
    """
    if keys is None:
        keys = []
    result = []
    for k, v in d.items():
        if isinstance(v, dict):
            result.extend(unnest(v, keys + [k]))
        else:
            result.append(tuple(keys + [k, v]))
    return result


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


def multikeysort(items: List[Dict], columns, _cmp=cmp, inplace=False):
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
    >>> assert all([cmp(total[i], total[i+1]) in (0,-1,)
    ...             for i in range(len(total)-1)])

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
    >>> assert all([cmp(total[i], total[i+1]) in (0, 1,)
    ...             for i in range(len(total)-1)])
    """
    if not isinstance(columns, (list, tuple)):
        columns = (columns,)

    m = re.compile(r'^-')
    known = set(collapse(*[list(d.keys()) for d in items]))
    columns = [x for x in columns if x and m.sub('', x) in known]

    i = operator.itemgetter
    comparers = [(i(m.sub('', col)), -1) if m.match(col) else (i(col), 1)
                 for col in columns]

    def comparer(left, right):
        comparer_iter = (_cmp(fn(left), fn(right)) * mult
                         for fn, mult in comparers)
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


def trace_key(d, attrname) -> List[List]:
    """Trace dictionary key in nested dictionary

    >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))))
    >>> trace_key(l,'f')
    [['a', 'b', 'c', 'd', 'e', 'f']]

    Multiple locations
    >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))), f=2)
    >>> trace_key(l,'f')
    [['a', 'b', 'c', 'd', 'e', 'f'], ['f']]

    With missing key
    >>> trace_key(l, 'g')
    Traceback (most recent call last):
    ...
    AttributeError: g
    """
    t = trace(d, attrname)
    if not t:
        raise AttributeError(attrname)
    return t


def trace_value(d, attrname) -> List:
    """Trace values returned by `trace key`

    >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))))
    >>> trace_value(l, 'f')
    [1]

    Multiple locations
    >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))), f=2)
    >>> trace_value(l,'f')
    [1, 2]

    With missing key
    >>> trace_value(l, 'g')
    Traceback (most recent call last):
    ...
    AttributeError: g
    """
    values = []
    t = trace_key(d, attrname)
    for i, result in enumerate(t):
        _node = d
        values.append(None)
        for key in result:
            _node = _node[key]
            values[i] = _node
    return values
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


# Database Utilities ..................................................... {{{1

def chunked(cursor, size=1000):
    while True:
        this_chunk = cursor.fetchmany(size)
        if not this_chunk:
            break
        yield from this_chunk

#  ....................................................................... }}}1
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
    [<class '....F'>,
     <class '....B'>,
     <class '....A'>,
     <class '....X'>,
     <class '....Y'>,
     <class '....Z'>,
     <class 'object'>]
    >>> class F_L:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=True)
    >>> class F_R:
    ...     def __init__(self):
    ...         extend_instance(self, B, left=False)
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
    >>> unnest(tree)
    [('a', 'apple'), ('b', 'c', 'd', 'dog')]

    Example 2:
    >>> vector2 = ['b', 'c', 'e']
    >>> value2 = 'egg'
    >>> tree = add_branch(tree, vector2, value2)
    >>> unnest(tree)
    [('a', 'apple'), ('b', 'c', 'd', 'dog'), ('b', 'c', 'e', 'egg')]

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
# Processes .............................................................. {{{1


def kill_proc(name=None, version=None, dry_run=False):
    """Generic kill process utilitiy
    """
    assert name or version, 'Need something to kill'
    _name = fr'.*{(name or "")}(\.exe)?$'
    match = False
    procs = []
    for proc in psutil.process_iter(attrs=['name']):
        try:
            cmd = ''.join(proc.cmdline())
        except:
            continue
        if _name and not re.match(_name, proc.name()):
            continue
        if version and version not in cmd:
            continue
        match = True
        if dry_run:
            return match
        procs.append(proc)
    gone, alive = psutil.wait_procs(procs, timeout=10)
    for p in alive:
        with suppress(Exception):
            p.kill()
    return match
#  ....................................................................... }}}1


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)

# vim: foldenable
