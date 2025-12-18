from __future__ import annotations

import copy
import inspect
import itertools
import logging
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any

from trace_dkey import trace

from libb._rust import multikeysort as _multikeysort_impl

logger = logging.getLogger(__name__)

__all__ = [
    'ismapping',
    'invert',
    'mapkeys',
    'mapvals',
    'flatten',
    'unnest',
    'replacekey',
    'replaceattr',
    'cmp',
    'multikeysort',
    'map',
    'get_attrs',
    'trace_key',
    'trace_value',
    'add_branch',
    'merge_dict',
]


def ismapping(something):
    """Check if something is a mapping (dict-like).

    :param something: Object to check.
    :returns: True if the object is a mapping.
    :rtype: bool

    Example::

        >>> ismapping(dict())
        True
    """
    return isinstance(something, Mapping)


def invert(dct):
    """Invert a dictionary, swapping keys and values.

    :param dict dct: Dictionary to invert.
    :returns: New dictionary with keys and values swapped.
    :rtype: dict

    Example::

        >>> invert({'a': 1, 'b': 2})
        {1: 'a', 2: 'b'}
    """
    return {v: k for k, v in list(dct.items())}


def mapkeys(func, dct):
    """Apply a function to all keys in a dictionary.

    :param func: Function to apply to each key.
    :param dict dct: Dictionary to transform.
    :returns: New dictionary with transformed keys.
    :rtype: dict

    Example::

        >>> mapkeys(str.upper, {'a': 1, 'b': 2})
        {'A': 1, 'B': 2}
    """
    return {func(key): val for key, val in list(dct.items())}


def mapvals(func, dct):
    """Apply a function to all values in a dictionary.

    :param func: Function to apply to each value.
    :param dict dct: Dictionary to transform.
    :returns: New dictionary with transformed values.
    :rtype: dict

    Example::

        >>> mapvals(lambda x: x * 2, {'a': 1, 'b': 2})
        {'a': 2, 'b': 4}
    """
    return {key: func(val) for key, val in list(dct.items())}


def flatten(kv, prefix=None):
    """Flatten a dictionary, recursively flattening nested dicts.

    Unlike `more_itertools.flatten <https://more-itertools.readthedocs.io/en/
    stable/api.html#more_itertools.flatten>`_, this operates on dictionaries
    rather than iterables. It recursively flattens nested dict keys by joining
    them with underscores (e.g., ``{'a': {'b': 1}}`` becomes ``('a_b', 1)``),
    whereas more_itertools.flatten removes one level of nesting from a list of
    lists.

    :param dict kv: Dictionary to flatten.
    :param list prefix: Internal prefix list for recursion (do not set manually).
    :yields: Tuples of (flattened_key, value).

    Example::

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
    """Recursively convert dict into list of tuples.

    :param dict d: Dictionary to unnest.
    :param list keys: Internal key accumulator (do not set manually).
    :returns: List of tuples representing paths to leaf values.
    :rtype: list

    Example::

        >>> unnest({'a': {'b': 1}, 'c': 2})
        [('a', 'b', 1), ('c', 2)]
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
    """Context manager for temporarily patching a dictionary value.

    :param dict d: Dictionary to patch.
    :param key: Key to temporarily replace.
    :param newval: Temporary value to set.

    Basic Usage::

        >>> f = dict(x=13)
        >>> with replacekey(f, 'x', 'pho'):
        ...     f['x']
        'pho'
        >>> f['x']
        13

    If the dict does not have the key set before, we return to that state::

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
    """Context manager for temporarily monkey patching an object attribute.

    :param obj: Object to patch.
    :param str attrname: Attribute name to temporarily replace.
    :param newval: Temporary value to set.

    Basic Usage::

        >>> class Foo: pass
        >>> f = Foo()
        >>> f.x = 13
        >>> with replaceattr(f, 'x', 'pho'):
        ...     f.x
        'pho'
        >>> f.x
        13

    If the obj did not have the attr set, we remove it::

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
    """Python 2 style cmp function with null value handling.

    Handles null values gracefully in sort comparisons.

    :param left: First value to compare.
    :param right: Second value to compare.
    :returns: -1 if left < right, 0 if equal, 1 if left > right.
    :rtype: int

    Example::

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
        _ = iter(left) and iter(right)
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


def multikeysort(items: list[dict], columns, inplace=False):
    """Sort list of dictionaries by list of keys.

    Equivalent to SQL ``ORDER BY`` - use no prefix for ascending, ``-`` prefix for descending.

    :param list items: List of dictionaries to sort.
    :param columns: List of column names to sort by (prefix with ``-`` for descending).
    :param bool inplace: If True, sort in place; otherwise return new sorted list.
    :returns: Sorted list if inplace=False, otherwise None.

    Basic Usage::

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

    Missing Columns are Ignored::

        >>> us = multikeysort(ds, ['missing',])
        >>> assert us[0]['total'] == 96.0
        >>> assert us[1]['total'] == 96.0
        >>> assert us[2]['total'] == 80.0
        >>> assert us[3]['total'] == None
        >>> assert us[4]['total'] == 80.0

    None Columns are Handled::

        >>> us = multikeysort(ds, None)
        >>> assert us[0]['total'] == 96.0
        >>> assert us[1]['total'] == 96.0
        >>> assert us[2]['total'] == 80.0
        >>> assert us[3]['total'] == None
        >>> assert us[4]['total'] == 80.0

    Descending Order with Inplace::

        >>> multikeysort(ds, ['-total', 'category'], inplace=True) # desc
        >>> total = [_['total'] for _ in ds]
        >>> assert all([cmp(total[i], total[i+1]) in (0, 1,)
        ...             for i in range(len(total)-1)])
    """
    return _multikeysort_impl(items, columns, inplace)


def map(func, *iterables):
    """Simulate a Python 2-like map with longest iterable behavior.

    Continues until the longest of the argument iterables is exhausted,
    extending the other arguments with None.

    :param func: Function to apply (or None for tuple aggregation).
    :param iterables: Iterables to map over.
    :returns: Iterator of mapped results.

    Example::

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
    """Get class attributes (excluding methods and dunders).

    :param type klazz: Class to inspect.
    :returns: List of (name, value) tuples for class attributes.
    :rtype: list

    Example::

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
    """Trace dictionary key in nested dictionary.

    :param dict d: Dictionary to search.
    :param str attrname: Key name to find.
    :returns: List of paths (as lists) to the key.
    :rtype: list[list]
    :raises AttributeError: If key is not found.

    Basic Usage::

        >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))))
        >>> trace_key(l,'f')
        [['a', 'b', 'c', 'd', 'e', 'f']]

    Multiple Locations::

        >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))), f=2)
        >>> trace_key(l,'f')
        [['a', 'b', 'c', 'd', 'e', 'f'], ['f']]

    With Missing Key::

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
    """Get values at all locations of a key in nested dictionary.

    :param dict d: Dictionary to search.
    :param str attrname: Key name to find.
    :returns: List of values found at each key location.
    :rtype: list
    :raises AttributeError: If key is not found.

    Basic Usage::

        >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))))
        >>> trace_value(l, 'f')
        [1]

    Multiple Locations::

        >>> l=dict(a=dict(b=dict(c=dict(d=dict(e=dict(f=1))))), f=2)
        >>> trace_value(l,'f')
        [1, 2]

    With Missing Key::

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
    """Insert a value into a dict at the path specified by vector.

    Given a dict, a vector, and a value, insert the value into the dict
    at the tree leaf specified by the vector. Recursive!

    :param dict tree: The data structure to insert the vector into.
    :param list vector: A list of values representing the path to the leaf node.
    :param value: The object to be inserted at the leaf.
    :returns: The dict with the value placed at the path specified.
    :rtype: dict

    .. note::
        Algorithm from https://stackoverflow.com/a/47276490

    Algorithm:
        - If we're at the leaf, add it as key/value to the tree
        - Else: If the subtree doesn't exist, create it.
        - Recurse with the subtree and the left shifted vector.
        - Return the tree.

    Useful for parsing ini files with dot-delimited keys::

        [app]
        site1.ftp.host = hostname
        site1.ftp.username = username
        site1.database.hostname = db_host

    Example 1::

        >>> tree = {'a': 'apple'}
        >>> vector = ['b', 'c', 'd']
        >>> value = 'dog'
        >>> tree = add_branch(tree, vector, value)
        >>> unnest(tree)
        [('a', 'apple'), ('b', 'c', 'd', 'dog')]

    Example 2::

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

    This function performs a deep merge of ``new`` into ``old``, handling nested
    dictionaries, iterables (like lists and tuples), and type mismatches gracefully.

    :param dict old: The dictionary to merge into (will be modified if inplace=True).
    :param dict new: The dictionary to merge from (remains unchanged).
    :param bool inplace: If True, modifies old in place; if False, returns a new merged dict.
    :returns: If inplace=False, returns the merged dictionary. Otherwise, returns None.

    Basic Nested Merge::

        >>> l1 = {'a': {'b': 1, 'c': 2}, 'b': 2}
        >>> l2 = {'a': {'a': 9}, 'c': 3}
        >>> merge_dict(l1, l2, inplace=False)
        {'a': {'b': 1, 'c': 2, 'a': 9}, 'b': 2, 'c': 3}
        >>> l1=={'a': {'b': 1, 'c': 2}, 'b': 2}
        True
        >>> l2=={'a': {'a': 9}, 'c': 3}
        True

    Multilevel Merging::

        >>> xx = {'a': {'b': 1, 'c': 2}, 'b': 2}
        >>> nice = {'a': {'a': 9}, 'c': 3}
        >>> merge_dict(xx, nice)
        >>> 'a' in xx['a']
        True
        >>> 'c' in xx
        True

    Values Get Overwritten::

        >>> warn = {'a': {'c': 9}, 'b': 3}
        >>> merge_dict(xx, warn)
        >>> xx['a']['c']
        9
        >>> xx['b']
        3

    Merges Iterables (preserving types when possible)::

        >>> l1 = {'a': {'c': [5, 2]}, 'b': 1}
        >>> l2 = {'a': {'c': [1, 2]}, 'b': 3}
        >>> merge_dict(l1, l2)
        >>> len(l1['a']['c'])
        4
        >>> l1['b']
        3

    Handles Type Mismatches (converts to lists)::

        >>> l1 = {'a': {'c': [5, 2]}, 'b': 1}
        >>> l3 = {'a': {'c': (1, 2,)}, 'b': 3}
        >>> merge_dict(l1, l3)
        >>> len(l1['a']['c'])
        4
        >>> isinstance(l1['a']['c'], list)
        True

    Handles None Values::

        >>> l1 = {'a': {'c': None}, 'b': 1}
        >>> l2 = {'a': {'c': [1, 2]}, 'b': 3}
        >>> merge_dict(l1, l2)
        >>> l1['a']['c']
        [1, 2]
    """
    from libb.iter import isiterable

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
