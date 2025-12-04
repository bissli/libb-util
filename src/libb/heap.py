import heapq

__all__ = [
    'ComparableHeap',
]


class ComparableHeap:
    """Heap with custom key comparator.

    Wraps heapq to add a keyed comparator function.

    :param list initial: Initial items for the heap.
    :param key: Key function for comparison (default: identity).

    .. note::
        Algorithm from https://stackoverflow.com/questions/8875706/heapq-with-custom-compare-predicate

    Example::

        >>> from datetime import datetime
        >>> ch=ComparableHeap(initial=[\
                {'dtm':datetime(2017,1,1,12,10,59),'val':'one'},\
                {'dtm':datetime(2017,1,1,12,10,58),'val':'two'}],\
                key=lambda f: f['dtm'])
        >>> ch.pop()
        {'dtm': datetime.datetime(2017, 1, 1, 12, 10, 58), 'val': 'two'}
        >>> ch.push({'val': 'three', 'dtm': datetime(2017,1,1,12,11,00)})
        >>> ch.pop()
        {'dtm': datetime.datetime(2017, 1, 1, 12, 10, 59), 'val': 'one'}
    """

    def __init__(self, initial=None, key=lambda x: x):
        self.key = key
        if initial:
            self._data = [(key(item), item) for item in initial]
            heapq.heapify(self._data)
        else:
            self._data = []

    def push(self, item):
        heapq.heappush(self._data, (self.key(item), item))

    def pop(self):
        return heapq.heappop(self._data)[1]


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
