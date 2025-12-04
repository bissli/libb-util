import logging
from collections.abc import Iterable, Iterator, MutableSet
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ['OrderedSet']


class OrderedSet(MutableSet):
    """A set that maintains insertion order using a doubly linked list.

    Provides set operations while preserving the order elements were added.

    .. note::
        Based on Raymond Hettinger's recipe from ActiveState.

    Features:
        - Combines set behavior (unique elements) with list behavior (order preservation)
        - Supports all standard set operations (union, intersection, difference)
        - Maintains insertion order for iteration and representation

    Example::

        >>> s = OrderedSet('abracadaba')
        >>> t = OrderedSet('simsalabim')
        >>> (s | t)
        OrderedSet(['a', 'b', 'r', 'c', 'd', 's', 'i', 'm', 'l'])
        >>> (s & t)
        OrderedSet(['a', 'b'])
        >>> (s - t)
        OrderedSet(['r', 'c', 'd'])
    """

    def __init__(self, iterable: Iterable[Any] = None) -> None:
        """Initialize an OrderedSet with optional iterable.

        Creates an empty ordered set or populates it from an iterable while
        preserving insertion order and removing duplicates.

        :param iterable: Optional sequence of elements to add.
        """
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self) -> int:
        """Return the number of elements in the set.

        :returns: Count of unique elements.
        :rtype: int
        """
        return len(self.map)

    def __contains__(self, key: Any) -> bool:
        """Check if an element exists in the set.

        :param key: Element to check for membership.
        :returns: True if the element is in the set.
        :rtype: bool
        """
        return key in self.map

    def add(self, key: Any) -> None:
        """Add an element to the end of the set if not already present.

        :param key: Element to add to the set.
        """
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key: Any) -> None:
        """Remove an element from the set if present.

        Does not raise an error if element is not found.

        :param key: Element to remove.
        """
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self) -> Iterator[Any]:
        """Iterate over elements in insertion order.

        :returns: Iterator yielding elements in order of addition.
        :rtype: Iterator
        """
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self) -> Iterator[Any]:
        """Iterate over elements in reverse insertion order.

        :returns: Iterator yielding elements in reverse order.
        :rtype: Iterator
        """
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last: bool = True) -> Any:
        """Remove and return an element from the set.

        :param bool last: If True, remove from end; if False, from beginning.
        :returns: The removed element.
        :raises KeyError: If the set is empty.
        """
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self) -> str:
        """Return string representation of the set.

        :returns: String showing class name and ordered elements.
        :rtype: str
        """
        if not self:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({list(self)!r})'

    def __eq__(self, other: object) -> bool:
        """Check equality with another set or OrderedSet.

        For OrderedSet comparison, both content and order must match.
        For regular set comparison, only content is considered.

        :param other: Object to compare with.
        :returns: True if sets are equal.
        :rtype: bool
        """
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
