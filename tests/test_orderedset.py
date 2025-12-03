import pytest

from libb import OrderedSet


class TestOrderedSet:
    """Tests for OrderedSet class."""

    def test_orderedset_creation(self):
        s = OrderedSet([1, 2, 3, 2, 1])
        assert list(s) == [1, 2, 3]

    def test_orderedset_add(self):
        s = OrderedSet()
        s.add(1)
        s.add(2)
        s.add(1)  # duplicate
        assert list(s) == [1, 2]

    def test_orderedset_discard(self):
        s = OrderedSet([1, 2, 3])
        s.discard(2)
        assert list(s) == [1, 3]

    def test_orderedset_discard_missing(self):
        s = OrderedSet([1, 2, 3])
        s.discard(99)  # Should not raise
        assert list(s) == [1, 2, 3]

    def test_orderedset_contains(self):
        s = OrderedSet([1, 2, 3])
        assert 2 in s
        assert 99 not in s

    def test_orderedset_len(self):
        s = OrderedSet([1, 2, 3])
        assert len(s) == 3

    def test_orderedset_iter(self):
        s = OrderedSet([3, 1, 2])
        assert list(s) == [3, 1, 2]

    def test_orderedset_reversed(self):
        s = OrderedSet([1, 2, 3])
        assert list(reversed(s)) == [3, 2, 1]

    def test_orderedset_pop_last(self):
        s = OrderedSet([1, 2, 3])
        item = s.pop()
        assert item == 3
        assert list(s) == [1, 2]

    def test_orderedset_pop_first(self):
        s = OrderedSet([1, 2, 3])
        item = s.pop(last=False)
        assert item == 1
        assert list(s) == [2, 3]

    def test_orderedset_equality(self):
        s1 = OrderedSet([1, 2, 3])
        s2 = OrderedSet([1, 2, 3])
        assert s1 == s2

    def test_orderedset_union(self):
        s1 = OrderedSet([1, 2])
        s2 = OrderedSet([2, 3])
        result = s1 | s2
        assert list(result) == [1, 2, 3]

    def test_orderedset_intersection(self):
        s1 = OrderedSet([1, 2, 3])
        s2 = OrderedSet([2, 3, 4])
        result = s1 & s2
        assert set(result) == {2, 3}

    def test_orderedset_pop_empty_raises(self):
        s = OrderedSet()
        with pytest.raises(KeyError, match='set is empty'):
            s.pop()

    def test_orderedset_repr_empty(self):
        s = OrderedSet()
        assert repr(s) == 'OrderedSet()'

    def test_orderedset_repr_with_items(self):
        s = OrderedSet([1, 2, 3])
        assert repr(s) == 'OrderedSet([1, 2, 3])'

    def test_orderedset_equality_with_regular_set(self):
        s1 = OrderedSet([1, 2, 3])
        s2 = {1, 2, 3}
        assert s1 == s2

    def test_orderedset_inequality_different_order(self):
        s1 = OrderedSet([1, 2, 3])
        s2 = OrderedSet([3, 2, 1])
        assert s1 != s2

    def test_orderedset_inequality_different_length(self):
        s1 = OrderedSet([1, 2, 3])
        s2 = OrderedSet([1, 2])
        assert s1 != s2


if __name__ == '__main__':
    pytest.main([__file__])
