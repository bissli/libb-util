import copy
import inspect
import itertools
import logging
import operator
import re
from collections.abc import Mapping
from contextlib import contextmanager
from functools import cmp_to_key
from typing import Any

from trace_dkey import trace

from libb.iterutils import collapse

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
    >>> import os, sys
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


def multikeysort(items: list[dict], columns, _cmp=cmp, inplace=False):
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
    if not isinstance(columns, list | tuple):
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


def trace_key(d, attrname) -> list[list]:
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


def trace_value(d, attrname) -> list:
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


# Define a type for dictionaries that can contain nested dictionaries
DictType = dict[str, Any]


def merge_dict(old: DictType, new: DictType, inplace: bool = True) -> DictType | None:
    """Recursively merge two dictionaries, including nested dictionaries and iterables.

    This function performs a deep merge of `new` into `old`, handling nested
    dictionaries, iterables (like lists and tuples), and type mismatches gracefully.

    Parameters
        old: The dictionary to merge into (will be modified if inplace=True)
        new: The dictionary to merge from (remains unchanged)
        inplace: If True, modifies old in place; if False, returns a new merged dict

    Returns
        If inplace=False, returns the merged dictionary. Otherwise, returns None.

    Examples

    Basic nested merge:
    >>> l1 = {'a': {'b': 1, 'c': 2}, 'b': 2}
    >>> l2 = {'a': {'a': 9}, 'c': 3}
    >>> merge_dict(l1, l2, inplace=False)
    {'a': {'b': 1, 'c': 2, 'a': 9}, 'b': 2, 'c': 3}
    >>> l1=={'a': {'b': 1, 'c': 2}, 'b': 2}
    True
    >>> l2=={'a': {'a': 9}, 'c': 3}
    True

    Multilevel merging:
    >>> xx = {'a': {'b': 1, 'c': 2}, 'b': 2}
    >>> nice = {'a': {'a': 9}, 'c': 3}
    >>> merge_dict(xx, nice)
    >>> 'a' in xx['a']
    True
    >>> 'c' in xx
    True

    Values get overwritten:
    >>> warn = {'a': {'c': 9}, 'b': 3}
    >>> merge_dict(xx, warn)
    >>> xx['a']['c']
    9
    >>> xx['b']
    3

    Merges iterables, preserving types when possible:
    >>> l1 = {'a': {'c': [5, 2]}, 'b': 1}
    >>> l2 = {'a': {'c': [1, 2]}, 'b': 3}
    >>> merge_dict(l1, l2)
    >>> len(l1['a']['c'])
    4
    >>> l1['b']
    3

    Handles type mismatches by converting to lists:
    >>> l1 = {'a': {'c': [5, 2]}, 'b': 1}
    >>> l3 = {'a': {'c': (1, 2,)}, 'b': 3}
    >>> merge_dict(l1, l3)
    >>> len(l1['a']['c'])
    4
    >>> isinstance(l1['a']['c'], list)
    True

    Handles None values:
    >>> l1 = {'a': {'c': None}, 'b': 1}
    >>> l2 = {'a': {'c': [1, 2]}, 'b': 3}
    >>> merge_dict(l1, l2)
    >>> l1['a']['c']
    [1, 2]
    """
    from libb.iterutils import isiterable

    if not inplace:
        old = copy.deepcopy(old)

    for key, new_val in new.items():
        old_val = old.get(key)

        # Case 1: Both values are dictionaries - recursively merge
        if ismapping(old_val) and ismapping(new_val):
            merge_dict(old_val, new_val, inplace=True)
            continue

        # Case 2: Target value is None - use source value directly
        if old_val is None:
            old[key] = new_val
            continue

        # Case 3: Both values are iterables (excluding strings) - combine them
        if isiterable(old_val) and isiterable(new_val) and not isinstance(new_val, str):
            try:
                old[key] = old_val + new_val
            except (TypeError, ValueError):
                old[key] = list(old_val) + list(new_val)
            continue

        # Case 4: Default case - overwrite target value
        old[key] = new_val

    if not inplace:
        return old


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
