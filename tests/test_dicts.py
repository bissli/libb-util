import pytest

from libb import add_branch, cmp, flatten, get_attrs, invert, ismapping
from libb import mapkeys, mapvals, merge_dict, multikeysort, replaceattr
from libb import replacekey, trace_key, trace_value, unnest
from libb.dicts import map as dict_map


class TestIsmapping:
    """Tests for ismapping function."""

    def test_ismapping_dict(self):
        assert ismapping({}) is True

    def test_ismapping_list(self):
        assert ismapping([]) is False

    def test_ismapping_string(self):
        assert ismapping('hello') is False


class TestInvert:
    """Tests for invert function."""

    def test_invert_basic(self):
        assert invert({'a': 1, 'b': 2}) == {1: 'a', 2: 'b'}

    def test_invert_empty(self):
        assert invert({}) == {}


class TestMapkeys:
    """Tests for mapkeys function."""

    def test_mapkeys_upper(self):
        assert mapkeys(str.upper, {'a': 1, 'b': 2}) == {'A': 1, 'B': 2}

    def test_mapkeys_empty(self):
        assert mapkeys(str.upper, {}) == {}


class TestMapvals:
    """Tests for mapvals function."""

    def test_mapvals_double(self):
        assert mapvals(lambda x: x * 2, {'a': 1, 'b': 2}) == {'a': 2, 'b': 4}

    def test_mapvals_empty(self):
        assert mapvals(lambda x: x * 2, {}) == {}


class TestFlatten:
    """Tests for flatten function."""

    def test_flatten_nested(self):
        data = {'event': 'Click', 'properties': {'user_id': '123', 'page': 'home'}}
        result = dict(flatten(data))
        assert result == {'event': 'Click', 'properties_user_id': '123', 'properties_page': 'home'}

    def test_flatten_simple(self):
        data = {'a': 1, 'b': 2}
        result = dict(flatten(data))
        assert result == {'a': 1, 'b': 2}


class TestUnnest:
    """Tests for unnest function."""

    def test_unnest_basic(self):
        d = {'a': {'b': 1}}
        result = unnest(d)
        assert result == [('a', 'b', 1)]

    def test_unnest_flat(self):
        d = {'a': 1, 'b': 2}
        result = unnest(d)
        assert ('a', 1) in result
        assert ('b', 2) in result


class TestReplacekey:
    """Tests for replacekey context manager."""

    def test_replacekey_restore(self):
        f = {'x': 13}
        with replacekey(f, 'x', 'pho'):
            assert f['x'] == 'pho'
        assert f['x'] == 13

    def test_replacekey_remove_new_key(self):
        f = {'x': 13}
        with replacekey(f, 'y', 'new'):
            assert f['y'] == 'new'
        assert 'y' not in f


class TestReplaceattr:
    """Tests for replaceattr context manager."""

    def test_replaceattr_restore(self):
        class Foo:
            pass
        f = Foo()
        f.x = 13
        with replaceattr(f, 'x', 'pho'):
            assert f.x == 'pho'
        assert f.x == 13

    def test_replaceattr_remove_new_attr(self):
        class Foo:
            pass
        f = Foo()
        f.x = 13
        with replaceattr(f, 'y', 'new'):
            assert f.y == 'new'
        assert not hasattr(f, 'y')


class TestCmp:
    """Tests for cmp function."""

    def test_cmp_none_comparisons(self):
        assert cmp(None, 2) == -1
        assert cmp(2, None) == 1
        assert cmp(None, None) == 0

    def test_cmp_numeric(self):
        assert cmp(-1, 2) == -1
        assert cmp(2, -1) == 1
        assert cmp(1, 1) == 0

    def test_cmp_iterables_with_none(self):
        # Test iterable comparisons with None values
        assert cmp([None], [None]) == 0  # Both have None
        assert cmp([None], [1]) == -1  # Left has None, right doesn't
        assert cmp([1], [None]) == 1  # Right has None, left doesn't
        assert cmp([1, 2], [1, 3]) == -1  # Normal comparison


class TestMultikeysort:
    """Tests for multikeysort function."""

    def test_multikeysort_basic(self):
        ds = [
            {'category': 'c1', 'total': 96.0},
            {'category': 'c2', 'total': 96.0},
            {'category': 'c3', 'total': 80.0},
        ]
        asc = multikeysort(ds, ['total', 'category'])
        assert asc[0]['total'] == 80.0

    def test_multikeysort_descending(self):
        ds = [
            {'category': 'c1', 'total': 96.0},
            {'category': 'c3', 'total': 80.0},
        ]
        desc = multikeysort(ds, ['-total'])
        assert desc[0]['total'] == 96.0

    def test_multikeysort_with_none(self):
        ds = [
            {'category': 'c1', 'total': 96.0},
            {'category': 'c4', 'total': None},
        ]
        result = multikeysort(ds, ['total'])
        assert result[0]['total'] is None

    def test_multikeysort_missing_column(self):
        ds = [{'category': 'c1', 'total': 96.0}]
        result = multikeysort(ds, ['missing'])
        assert result[0]['total'] == 96.0

    def test_multikeysort_single_column_string(self):
        # Test with single string column instead of list
        ds = [
            {'category': 'c1', 'total': 96.0},
            {'category': 'c3', 'total': 80.0},
        ]
        result = multikeysort(ds, 'total')
        assert result[0]['total'] == 80.0

    def test_multikeysort_inplace(self):
        ds = [
            {'category': 'c1', 'total': 96.0},
            {'category': 'c3', 'total': 80.0},
        ]
        multikeysort(ds, ['total'], inplace=True)
        assert ds[0]['total'] == 80.0


class TestDictMap:
    """Tests for map function."""

    def test_dict_map_basic(self):
        def foo(a, b):
            if b is not None:
                return a - b
            return -a
        result = list(dict_map(foo, range(5), [3, 2, 1]))
        assert result == [-3, -1, 1, -3, -4]

    def test_dict_map_none_func(self):
        # When func is None, returns zipped tuples
        result = list(dict_map(None, [1, 2, 3], ['a', 'b']))
        assert result == [(1, 'a'), (2, 'b'), (3, None)]


class TestGetAttrs:
    """Tests for get_attrs function."""

    def test_get_attrs_basic(self):
        class MyClass:
            a = '12'
            b = '34'

            def myfunc(self):
                return self.a
        result = get_attrs(MyClass)
        assert ('a', '12') in result
        assert ('b', '34') in result


class TestTraceKey:
    """Tests for trace_key function."""

    def test_trace_key_nested(self):
        l = {'a': {'b': {'c': {'d': {'e': {'f': 1}}}}}}
        assert trace_key(l, 'f') == [['a', 'b', 'c', 'd', 'e', 'f']]

    def test_trace_key_multiple(self):
        l = {'a': {'b': {'f': 1}}, 'f': 2}
        result = trace_key(l, 'f')
        assert len(result) == 2

    def test_trace_key_missing(self):
        l = {'a': 1}
        with pytest.raises(AttributeError):
            trace_key(l, 'missing')


class TestTraceValue:
    """Tests for trace_value function."""

    def test_trace_value_nested(self):
        l = {'a': {'b': {'c': {'d': {'e': {'f': 1}}}}}}
        assert trace_value(l, 'f') == [1]

    def test_trace_value_multiple(self):
        l = {'a': {'b': {'f': 1}}, 'f': 2}
        result = trace_value(l, 'f')
        assert 1 in result
        assert 2 in result


class TestAddBranch:
    """Tests for add_branch function."""

    def test_add_branch_basic(self):
        tree = {'a': 'apple'}
        vector = ['b', 'c', 'd']
        value = 'dog'
        tree = add_branch(tree, vector, value)
        assert tree['b']['c']['d'] == 'dog'
        assert tree['a'] == 'apple'


class TestMergeDict:
    """Tests for merge_dict function."""

    def test_merge_dict_nested(self):
        l1 = {'a': {'b': 1, 'c': 2}, 'b': 2}
        l2 = {'a': {'a': 9}, 'c': 3}
        result = merge_dict(l1, l2, inplace=False)
        assert result['a']['a'] == 9
        assert result['a']['b'] == 1
        assert result['c'] == 3

    def test_merge_dict_inplace(self):
        xx = {'a': {'b': 1, 'c': 2}, 'b': 2}
        nice = {'a': {'a': 9}, 'c': 3}
        merge_dict(xx, nice)
        assert 'a' in xx['a']
        assert 'c' in xx

    def test_merge_dict_overwrite(self):
        xx = {'a': {'c': 2}}
        warn = {'a': {'c': 9}}
        merge_dict(xx, warn)
        assert xx['a']['c'] == 9

    def test_merge_dict_iterables(self):
        l1 = {'a': {'c': [5, 2]}, 'b': 1}
        l2 = {'a': {'c': [1, 2]}, 'b': 3}
        merge_dict(l1, l2)
        assert len(l1['a']['c']) == 4
        assert l1['b'] == 3

    def test_merge_dict_none_values(self):
        l1 = {'a': {'c': None}, 'b': 1}
        l2 = {'a': {'c': [1, 2]}, 'b': 3}
        merge_dict(l1, l2)
        assert l1['a']['c'] == [1, 2]

    def test_merge_dict_incompatible_iterables(self):
        # Test when iterables can't be directly added (TypeError/ValueError)
        # Sets can't be added with +, need to be converted to lists
        l1 = {'a': {1, 2}}
        l2 = {'a': {3, 4}}
        merge_dict(l1, l2)
        assert len(l1['a']) == 4


if __name__ == '__main__':
    pytest.main([__file__])
