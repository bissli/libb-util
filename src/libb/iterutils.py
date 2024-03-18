import itertools
import logging
from collections.abc import Iterable

import more_itertools

logger = logging.getLogger(__name__)

__all__ = [
    'compact',
    'hashby',
    'infinite_iterator',
    'iscollection',
    'isiterable',
    'unique',
    'unique_iter',
    ]


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


unique_iter = more_itertools.unique_everseen


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


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
