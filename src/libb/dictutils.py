import inspect
import itertools
import json
import logging
import operator
import os  # noqa
import re
import sys  # noqa
from abc import ABCMeta
from collections.abc import Mapping, MutableMapping
from contextlib import contextmanager
from functools import cmp_to_key
from typing import Dict, List

from libb.iterutils import collapse
from trace_dkey import trace

logger = logging.getLogger(__name__)


def ismapping(something):
    """Does this look kinda sorta like a dict?

    >>> ismapping(dict())
    True
    """
    return isinstance(something, Mapping)


def invert(dct):
    return {v: k for k, v in list(dct.items())}


def mapkeys(func, dct):
    return {func(key): val for key, val in list(dct.items())}


def mapvals(func, dct):
    return {key: func(val) for key, val in list(dct.items())}


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
        elif prefix:
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
        if None in left and None not in right:
            return -1
        if None not in left and None in right:
            return 1
        return _cmp(left, right)
    except TypeError:
        pass

    if left is None and right is None:
        return 0
    if left is None and right is not None:
        return -1
    if left is not None and right is None:
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
    known = set(collapse([list(d.keys()) for d in items]))
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
    from libb.iterutils import isiterable
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
    >>> 'x' in d
    True
    >>> 'w' in d
    False
    >>> d.get('x')
    10
    >>> d.get('w')
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

    >>> a.b
    2
    >>> a['b']
    2
    >>> 'c' in a
    False
    >>> 'b' in a
    True
    >>> a.get('b')
    2
    >>> a.get('c')
    """

    def __getattr__(self, attrname):
        try:
            return attrdict.__getattr__(self, attrname)
        except AttributeError:
            return

    def __getitem__(self, attrname):
        try:
            return attrdict.__getitem__(self, attrname)
        except AttributeError:
            return


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


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
