import pytest

from libb import align_iterdict, backfill, backfill_iterdict, chunked
from libb import coalesce, collapse, compact, getitem, hashby
from libb import infinite_iterator, iscollection, isiterable, issequence, peel
from libb import rpeel, same_order, unique
from libb.iter import negate_permute  # Internal function


class TestTypeChecks:
    """Tests for type checking functions."""

    def test_isiterable_with_list(self):
        assert isiterable([1, 2, 3]) is True

    def test_isiterable_with_tuple(self):
        assert isiterable((1, 2, 3)) is True

    def test_isiterable_with_string(self):
        assert isiterable('hello') is False

    def test_isiterable_with_object(self):
        assert isiterable(object()) is False

    def test_isiterable_with_generator(self):
        assert isiterable(x for x in range(3)) is True

    def test_issequence_with_list(self):
        assert issequence([1, 2, 3]) is True

    def test_issequence_with_tuple(self):
        assert issequence((1, 2, 3)) is True

    def test_issequence_with_string(self):
        assert issequence('hello') is False

    def test_issequence_with_range(self):
        assert issequence(range(10)) is True

    def test_iscollection_with_list(self):
        assert iscollection([1, 2, 3]) is True

    def test_iscollection_with_string(self):
        assert iscollection('hello') is False

    def test_iscollection_with_range(self):
        assert iscollection(range(10)) is True


class TestUnique:
    """Tests for unique function."""

    def test_unique_basic(self):
        assert unique([9, 0, 2, 1, 0]) == [9, 0, 2, 1]

    def test_unique_with_key(self):
        assert unique(['Foo', 'foo', 'bar'], key=lambda s: s.lower()) == ['Foo', 'bar']

    def test_unique_empty_list(self):
        assert unique([]) == []

    def test_unique_all_same(self):
        assert unique([1, 1, 1, 1]) == [1]

    def test_unique_with_unhashable(self):
        result = unique(([1, 2], [2, 3], [1, 2]), key=tuple)
        assert result == [[1, 2], [2, 3]]


class TestCompact:
    """Tests for compact function."""

    def test_compact_removes_none(self):
        assert compact([1, None, 2, None, 3]) == (1, 2, 3)

    def test_compact_removes_zero(self):
        # Note: compact also removes zero!
        assert compact([0, 2, 3, 4, None, 5]) == (2, 3, 4, 5)

    def test_compact_empty(self):
        assert compact([]) == ()


class TestCollapse:
    """Tests for collapse function."""

    def test_collapse_nested_lists(self):
        iterable = [(1, 2), ([3, 4], [[5], [6]])]
        assert list(collapse(iterable)) == [1, 2, 3, 4, 5, 6]

    def test_collapse_with_strings(self):
        iterable = [('a', ['b']), ('c', ['d'])]
        assert list(collapse(iterable)) == ['a', 'b', 'c', 'd']

    def test_collapse_preserves_dicts(self):
        iterable = (({'a': 'foo'},),)
        assert list(collapse(iterable)) == [{'a': 'foo'}]

    def test_collapse_complex(self):
        l1 = ['a', ['b', ('c', 'd')]]
        l2 = [0, 1, (2, 3), [[4, 5, (6, 7, (8,), [9]), 10]], (11,)]
        assert list(collapse([l1, -2, -1, l2])) == ['a', 'b', 'c', 'd', -2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]


class TestPeel:
    """Tests for peel and rpeel functions."""

    def test_peel_mixed(self):
        result = list(peel(['a', ('', 'b'), 'c']))
        assert result == [('a', 'a'), ('', 'b'), ('c', 'c')]

    def test_peel_empty(self):
        assert list(peel([])) == []

    def test_rpeel_mixed(self):
        result = list(rpeel(['a', ('', 'b'), 'c']))
        assert result == ['a', 'b', 'c']

    def test_rpeel_empty(self):
        assert list(rpeel([])) == []


class TestSameOrder:
    """Tests for same_order function."""

    def test_same_order_true(self):
        r = ['x', 'y', 'z']
        c = ['x', 'a', 'b', 'c', 'y', 'd', 'e', 'f', 'z', 'h']
        assert same_order(r, c) is True

    def test_same_order_false(self):
        r = ['x', 'y', 'z']
        c = ['x', 'a', 'b', 'c', 'z', 'd', 'e', 'f', 'y', 'h']
        assert same_order(r, c) is False

    def test_same_order_missing_element(self):
        r = ['x', 'y', 'z']
        c = ['x', 'y']
        assert same_order(r, c) is False


class TestCoalesce:
    """Tests for coalesce function."""

    def test_coalesce_first_non_none(self):
        assert coalesce(None, None, 1, 2) == 1

    def test_coalesce_all_none(self):
        assert coalesce(None, None, None) is None

    def test_coalesce_first_value(self):
        assert coalesce(1, 2, 3) == 1

    def test_coalesce_empty(self):
        assert coalesce() is None


class TestGetitem:
    """Tests for getitem function."""

    def test_getitem_valid_index(self):
        assert getitem([1, 2, 3], 1) == 2

    def test_getitem_out_of_range(self):
        assert getitem([1, 2, 3], 10) is None

    def test_getitem_negative_valid(self):
        assert getitem([1, 2, 3], -1) == 3

    def test_getitem_negative_out_of_range(self):
        assert getitem([1, 2, 3], -100) is None

    def test_getitem_with_default(self):
        assert getitem([1, 2, 3], 10, default='missing') == 'missing'


class TestBackfill:
    """Tests for backfill function."""

    def test_backfill_with_nones(self):
        assert backfill([None, None, 1, 2, 3, None, 4]) == [1, 1, 1, 2, 3, 3, 4]

    def test_backfill_no_nones(self):
        assert backfill([1, 2, 3]) == [1, 2, 3]

    def test_backfill_all_nones(self):
        assert backfill([None, None, None]) == [None, None, None]

    def test_backfill_empty(self):
        assert backfill([]) == []

    def test_backfill_trailing_none(self):
        assert backfill([1, 2, 3, None]) == [1, 2, 3, 3]


class TestBackfillIterdict:
    """Tests for backfill_iterdict function."""

    def test_backfill_iterdict_basic(self):
        result = backfill_iterdict([
            {'a': 1, 'b': None},
            {'a': 4, 'b': 2},
            {'a': None, 'b': None},
            {'a': 3, 'b': None}
        ])
        assert result == [{'a': 1, 'b': 2}, {'a': 4, 'b': 2}, {'a': 4, 'b': 2}, {'a': 3, 'b': 2}]

    def test_backfill_iterdict_empty(self):
        assert backfill_iterdict([]) == []

    def test_backfill_iterdict_no_nones(self):
        result = backfill_iterdict([
            {'a': 9, 'b': 2},
            {'a': 4, 'b': 1}
        ])
        assert result == [{'a': 9, 'b': 2}, {'a': 4, 'b': 1}]


class TestHashby:
    """Tests for hashby function."""

    def test_hashby_basic(self):
        items = [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]
        result = hashby(items, lambda x: x['id'])
        assert result == {1: {'id': 1, 'name': 'a'}, 2: {'id': 2, 'name': 'b'}}


class TestInfiniteIterator:
    """Tests for infinite_iterator function."""

    def test_infinite_iterator_cycles(self):
        ii = infinite_iterator([1, 2, 3, 4, 5])
        result = [next(ii) for _ in range(9)]
        assert result == [1, 2, 3, 4, 5, 1, 2, 3, 4]


class TestChunked:
    """Tests for chunked function (from more_itertools)."""

    def test_chunked_basic(self):
        result = list(chunked([1, 2, 3, 4, 5], 2))
        assert result == [[1, 2], [3, 4], [5]]


class TestNegatePermute:
    """Tests for negate_permute function."""

    def test_negate_permute_basic(self):
        result = next(negate_permute(1, 2))
        assert result == (-1, 1, -2, 2)

    def test_negate_permute_with_infinity(self):
        result = next(negate_permute(-float('inf'), 0))
        assert result == (float('inf'), -float('inf'), 0, 0)


class TestSameOrder:
    """Tests for same_order function."""

    def test_same_order_element_not_in_comp(self):
        # Test case where reference element is not in comparison list
        assert same_order([1, 2, 3], [4, 5, 6]) is False
        assert same_order([1, 3], [2, 3]) is False

    def test_same_order_comp_shorter_than_ref(self):
        # Test case where comp list is shorter than ref list
        assert same_order([1, 2, 3, 4], [1, 2]) is False

    def test_same_order_in_order(self):
        # Test case where elements are in order
        assert same_order([1, 2, 3], [1, 2, 3, 4, 5]) is True
        assert same_order(['a', 'b'], ['a', 'x', 'b', 'y']) is True

    def test_same_order_out_of_order(self):
        # Test case where elements are not in order
        assert same_order([1, 2, 3], [3, 2, 1]) is False


class TestAlignIterdict:
    """Tests for align_iterdict function."""

    def test_align_iterdict_basic(self):
        result = list(zip(*align_iterdict(
            [{'a': 1}, {'a': 2}, {'a': 5}],
            [{'b': 5}],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
        )))
        assert result == [({'a': 5},), ({'b': 5},)]

    def test_align_iterdict_a_exhausted_first(self):
        # Test when iterator A runs out before B
        result = list(align_iterdict(
            [{'a': 1}],
            [{'b': 1}, {'b': 2}, {'b': 3}],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
        ))
        assert len(result) == 1
        assert result[0] == ({'a': 1}, {'b': 1})

    def test_align_iterdict_b_exhausted_first(self):
        # Test when iterator B runs out before A
        result = list(align_iterdict(
            [{'a': 1}, {'a': 2}, {'a': 3}],
            [{'b': 1}],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
        ))
        assert len(result) == 1
        assert result[0] == ({'a': 1}, {'b': 1})

    def test_align_iterdict_with_tolerance(self):
        # Test alignment with tolerance
        result = list(align_iterdict(
            [{'a': 1}, {'a': 5}, {'a': 10}],
            [{'b': 2}, {'b': 6}, {'b': 11}],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
            tolerance=1,
        ))
        assert len(result) >= 1  # At least some matches

    def test_align_iterdict_empty_a(self):
        # Test when iterator A is empty - triggers StopIteration on first try
        result = list(align_iterdict(
            [],
            [{'b': 1}],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
        ))
        assert result == []

    def test_align_iterdict_empty_b(self):
        # Test when iterator B is empty - triggers StopIteration
        result = list(align_iterdict(
            [{'a': 1}],
            [],
            a='a',
            b='b',
            diff=lambda x, y: x - y,
        ))
        assert result == []


if __name__ == '__main__':
    pytest.main([__file__])
