import itertools
import logging
from collections.abc import Iterable

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
    'partition',
    'roundrobin',
    'unique',
    'unique_iter',
    ]


chunked = _more_itertools.chunked
chunked_even = _more_itertools.chunked_even
grouper = _more_itertools.grouper
partition = _more_itertools.partition
roundrobin = _more_itertools.roundrobin
unique_iter = _more_itertools.unique_everseen


def isiterable(obj):
    """Check for iterable type

    >>> isiterable([])
    True
    >>> isiterable(object())
    False
    """
    return isinstance(obj, Iterable) and not isinstance(obj, str)


def iscollection(obj):
    """Check that is both an iterable and not a string

    >>> iscollection(object())
    False
    >>> iscollection(range(10))
    True
    >>> iscollection('hello')
    False
    """
    return isiterable(obj) and not isinstance(obj, str)


def unique(iterable, key=None):
    """Removes duplicate elements from a list while preserving the
    order of the rest.

    >>> unique([9,0,2,1,0])
    [9, 0, 2, 1]

    The value of the optional `key` parameter should be a function that
    takes a single argument and returns a key to test the uniqueness.

    >>> unique(['Foo', 'foo', 'bar'], key=lambda s: s.lower())
    ['Foo', 'bar']

    Unbashable items can be used, but use hashing keys to improve speed.

    >>> unique(([1, 2],[2, 3],[1, 2]), key=tuple)
    [[1, 2], [2, 3]]
    >>> unique(({1,2,3},{4,5,6},{1,2,3}), key=frozenset)
    [{1, 2, 3}, {4, 5, 6}]
    >>> unique(({'a':1,'b':2},{'a':3,'b':4},{'a':1,'b':2}), key=lambda x: frozenset(x.items()))
    [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
    """
    return list(unique_iter(iterable, key))


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


def collapse(*args, base_type=(tuple, list)):
    """Recursive flatten of list of lists, returns a generator
    in original order. Similar to more_itertools.collapse.

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


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
