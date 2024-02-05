import itertools
import logging
from collections import defaultdict
from collections.abc import Iterable

import more_itertools

logger = logging.getLogger(__name__)


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


if __name__ == '__main__':
    __import__('doctest').testmod()
