import pytest

from libb import ComparableHeap


class TestComparableHeap:
    """Tests for ComparableHeap class."""

    def test_comparable_heap_min(self):
        heap = ComparableHeap(initial=[(5, 'e'), (1, 'a'), (3, 'c')])
        # Default is min-heap
        assert heap.pop() == (1, 'a')

    def test_comparable_heap_push(self):
        heap = ComparableHeap()
        heap.push((3, 'c'))
        heap.push((1, 'a'))
        heap.push((2, 'b'))
        assert heap.pop() == (1, 'a')

    def test_comparable_heap_with_key(self):
        # Max-heap using negative key
        heap = ComparableHeap(key=lambda x: -x[0])
        heap.push((1, 'a'))
        heap.push((3, 'c'))
        heap.push((2, 'b'))
        assert heap.pop() == (3, 'c')

    def test_comparable_heap_with_dict(self):
        from datetime import datetime
        heap = ComparableHeap(
            initial=[
                {'dtm': datetime(2017, 1, 1, 12, 10, 59), 'val': 'one'},
                {'dtm': datetime(2017, 1, 1, 12, 10, 58), 'val': 'two'},
            ],
            key=lambda f: f['dtm']
        )
        result = heap.pop()
        assert result['val'] == 'two'  # Earlier time comes first


if __name__ == '__main__':
    pytest.main([__file__])
