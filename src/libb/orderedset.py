import logging
from collections.abc import MutableSet, Iterable, Iterator
from typing import Any, Union

logger = logging.getLogger(__name__)

__all__ = ['OrderedSet']


class OrderedSet(MutableSet):
    """A set that maintains insertion order using a doubly linked list.

    Provides set operations while preserving the order elements were added.
    Based on Raymond Hettinger's recipe from ActiveState.
    - Combines the behavior of sets (unique elements) with lists (order preservation)
    - Supports all standard set operations (union, intersection, difference)
    - Maintains insertion order for iteration and representation

    Examples

    Basic usage:
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

        Parameters
            iterable: Optional sequence of elements to add to the set

        Returns
            None
        """
        self.end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self) -> int:
        """Return the number of elements in the set.

        Returns
            The count of unique elements in the set
        """
        return len(self.map)

    def __contains__(self, key: Any) -> bool:
        """Check if an element exists in the set.

        Parameters
            key: The element to check for membership

        Returns
            True if the element is in the set, False otherwise
        """
        return key in self.map

    def add(self, key: Any) -> None:
        """Add an element to the set.

        Adds the element to the end of the ordered set if not already present.
        If the element already exists, the set remains unchanged.

        Parameters
            key: The element to add to the set

        Returns
            None
        """
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key: Any) -> None:
        """Remove an element from the set if present.

        Removes the specified element from the set without raising an error
        if the element is not found.

        Parameters
            key: The element to remove from the set

        Returns
            None
        """
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self) -> Iterator[Any]:
        """Return an iterator over the set elements in insertion order.

        Returns
            An iterator that yields elements in the order they were added
        """
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self) -> Iterator[Any]:
        """Return an iterator over the set elements in reverse insertion order.

        Returns
            An iterator that yields elements in reverse order of addition
        """
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last: bool = True) -> Any:
        """Remove and return an element from the set.

        Removes and returns either the last or first element depending on
        the last parameter value.

        Parameters
            last: If True, remove from the end; if False, remove from the beginning

        Returns
            The removed element

        Raises
            KeyError: If the set is empty
        """
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self) -> str:
        """Return the string representation of the set.

        Returns
            A string showing the class name and ordered list of elements
        """
        if not self:
            return f'{self.__class__.__name__}()'
        return f'{self.__class__.__name__}({list(self)!r})'

    def __eq__(self, other: Any) -> bool:
        """Check equality with another set or OrderedSet.

        For OrderedSet comparison, both content and order must match.
        For regular set comparison, only content is considered.

        Parameters
            other: The object to compare with

        Returns
            True if the sets are equal according to the comparison rules
        """
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
