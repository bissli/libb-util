from __future__ import annotations

import itertools
import logging
from collections.abc import Iterable, Sequence

import more_itertools as _more_itertools

logger = logging.getLogger(__name__)

__all__ = [
    'chunked',
    'chunked_even',
    'collapse',
    'compact',
    'grouper',
    'hashby',
    'infinite_iterator',
    'iscollection',
    'isiterable',
    'issequence',
    'partition',
    'peel',
    'roundrobin',
    'rpeel',
    'unique',
    'unique_iter',
    'same_order',
    'coalesce',
    'getitem',
    'backfill',
    'backfill_iterdict',
    'align_iterdict',
    ]


#: Split iterable into chunks of length n. See :func:`more_itertools.chunked`.
chunked = _more_itertools.chunked
#: Split iterable into n chunks of roughly equal size. See :func:`more_itertools.chunked_even`.
chunked_even = _more_itertools.chunked_even
#: Collect data into fixed-length chunks. See :func:`more_itertools.grouper`.
grouper = _more_itertools.grouper
#: Partition items into those where pred is False/True. See :func:`more_itertools.partition`.
partition = _more_itertools.partition
#: Interleave items from multiple iterables. See :func:`more_itertools.roundrobin`.
roundrobin = _more_itertools.roundrobin
#: Yield unique elements, preserving order. See :func:`more_itertools.unique_everseen`.
unique_iter = _more_itertools.unique_everseen


def isiterable(obj):
    """Check if object is iterable (excluding strings).

    :param obj: Object to check.
    :returns: True if iterable and not a string.
    :rtype: bool

    Example::

        >>> isiterable([])
        True
        >>> isiterable(tuple())
        True
        >>> isiterable(object())
        False
        >>> isiterable('foo')
        False

    Note: DataFrames and arrays are iterable::

        >>> import pandas as pd
        >>> isiterable(pd.DataFrame([['foo', 1]], columns=['key', 'val']))
        True
        >>> import numpy as np
        >>> isiterable(np.array([1,2,3]))
        True
    """
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def issequence(obj):
    """Check if object is a sequence (excluding strings).

    :param obj: Object to check.
    :returns: True if sequence and not a string.
    :rtype: bool

    Example::

        >>> issequence([])
        True
        >>> issequence(tuple())
        True
        >>> issequence('foo')
        False
        >>> issequence(object())
        False

    Note: DataFrames and arrays are NOT sequences::

        >>> import pandas as pd
        >>> issequence(pd.DataFrame([['foo', 1]], columns=['key', 'val']))
        False
        >>> import numpy as np
        >>> issequence(np.array([1,2,3]))
        False
    """
    return isinstance(obj, Sequence) and not isinstance(obj, str)


def iscollection(obj):
    """Check if object is a collection (iterable and not a string).

    :param obj: Object to check.
    :returns: True if collection.
    :rtype: bool

    Example::

        >>> iscollection(object())
        False
        >>> iscollection(range(10))
        True
        >>> iscollection('hello')
        False
    """
    return isiterable(obj) and not isinstance(obj, str)


def unique(iterable, key=None):
    """Remove duplicate elements while preserving order.

    Unlike `more_itertools.unique <https://more-itertools.readthedocs.io/en/
    stable/api.html#more_itertools.unique>`_, this preserves the original
    insertion order rather than returning elements in sorted order. Internally
    uses :func:`more_itertools.unique_everseen`. Returns a list instead of a
    generator.

    :param iterable: Iterable to deduplicate.
    :param key: Optional function to compute uniqueness key.
    :returns: List of unique elements.
    :rtype: list

    Basic Usage::

        >>> unique([9,0,2,1,0])
        [9, 0, 2, 1]

    With Key Function::

        >>> unique(['Foo', 'foo', 'bar'], key=lambda s: s.lower())
        ['Foo', 'bar']

    Unhashable Items (use hashing keys for better performance)::

        >>> unique(([1, 2],[2, 3],[1, 2]), key=tuple)
        [[1, 2], [2, 3]]
        >>> unique(({1,2,3},{4,5,6},{1,2,3}), key=frozenset)
        [{1, 2, 3}, {4, 5, 6}]
        >>> unique(({'a':1,'b':2},{'a':3,'b':4},{'a':1,'b':2}), key=lambda x: frozenset(x.items()))
        [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
    """
    return list(unique_iter(iterable, key))


def compact(iterable):
    """Remove falsy values from an iterable (including None and 0).

    :param iterable: Iterable to filter.
    :returns: Tuple of truthy values.
    :rtype: tuple

    .. warning::
        This also removes zero!

    Example::

        >>> compact([0,2,3,4,None,5])
        (2, 3, 4, 5)
    """
    return tuple(item for item in iterable if item)


def hashby(iterable, keyfunc):
    """Create a dictionary from iterable using a key function.

    :param iterable: Items to hash.
    :param keyfunc: Function to extract key from each item.
    :returns: Dictionary mapping keys to items.
    :rtype: dict

    Example::

        >>> items = [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]
        >>> hashby(items, lambda x: x['id'])
        {1: {'id': 1, 'name': 'a'}, 2: {'id': 2, 'name': 'b'}}
    """
    return {keyfunc(item): item for item in iterable}


def negate_permute(*items):
    """Generate permutations of items with each value negated.

    For each item, yields permutations with positive and negative versions.

    :param items: Items to permute.
    :yields: Tuples of permuted values.

    Example::

        >>> next(negate_permute(1, 2))
        (-1, 1, -2, 2)
        >>> next(negate_permute(-float('inf'), 0))
        (inf, -inf, 0, 0)
    """
    yield from itertools.permutations(itertools.chain(*((-a, a) for a in items)))


def infinite_iterator(iterable):
    """Create an iterator that cycles infinitely through items.

    :param iterable: Sequence to cycle through.
    :returns: Generator that cycles forever.

    Example::

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


def collapse(*args, base_type=(tuple, list)):
    """Recursively flatten nested lists/tuples into a single generator.

    Unlike `more_itertools.collapse <https://more-itertools.readthedocs.io/en/
    stable/api.html#more_itertools.collapse>`_, this function takes variadic
    ``*args`` instead of a single iterable, and ``base_type`` specifies which
    types TO flatten (default: tuple, list) rather than which types to exclude.
    Also does not support a ``levels`` parameter.

    :param args: Items to collapse.
    :param base_type: Types to recursively expand (default: tuple, list).
    :returns: Generator of flattened items.

    Example::

        >>> l1 = ['a', ['b', ('c', 'd')]]
        >>> l2 = [0, 1, (2, 3), [[4, 5, (6, 7, (8,), [9]), 10]], (11,)]
        >>> list(collapse([l1, -2, -1, l2]))
        ['a', 'b', 'c', 'd', -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        >>> iterable = [(1, 2), ([3, 4], [[5], [6]])]
        >>> list(collapse(iterable))
        [1, 2, 3, 4, 5, 6]
        >>> iterable = [('a', ['b']), ('c', ['d'])]
        >>> list(collapse(iterable))
        ['a', 'b', 'c', 'd']
        >>> iterable = (({'a': 'foo', 'b': 'bar', 'c': 'baz'},),)
        >>> list(collapse(iterable))
        [{'a': 'foo', 'b': 'bar', 'c': 'baz'}]
    """
    return (e for a in args for e in (collapse(*a) if isinstance(a, base_type) else (a,)))


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


def coalesce(*args):
    """Return first non-None value.

    Example::

        >>> coalesce(None, None, 1, 2)
        1
        >>> coalesce(None, None) is None
        True
        >>> coalesce(0, 1, 2)
        0
    """
    return next((a for a in args if a is not None), None)


def getitem(sequence, index, default=None):
    """Safe sequence indexing with default value

    >>> getitem([1, 2, 3], 1)
    2
    >>> getitem([1, 2, 3], 10) is None
    True
    >>> getitem([1, 2, 3], -1)
    3
    >>> getitem([1, 2, 3], -100) is None
    True
    """
    try:
        return sequence[index]
    except IndexError:
        return default


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
            logger.debug(f'Aligned iters to A {this_a.get(attr_a)} B {this_b.get(attr_b)}')
            yield this_a, this_b
            try:
                this_a, this_b = next(gen_a), next(gen_b)
            except StopIteration:
                break


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
