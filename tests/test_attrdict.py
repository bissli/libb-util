import abc
import copy

import pytest

from libb import CaseInsensitiveDict, MutableDict, attrdict, bidict, emptydict
from libb import lazydict


class TestAttrdict:
    """Tests for attrdict class."""

    def test_attrdict_get_attr(self):
        d = attrdict(x=10, y='foo')
        assert d.x == 10

    def test_attrdict_get_item(self):
        d = attrdict(x=10, y='foo')
        assert d['x'] == 10

    def test_attrdict_set_attr(self):
        d = attrdict(x=10, y='foo')
        d.y = 'baa'
        assert d['y'] == 'baa'

    def test_attrdict_copy(self):
        d = attrdict(x=10)
        g = d.copy()
        g.x = 11
        assert d.x == 10

    def test_attrdict_contains(self):
        d = attrdict(x=10)
        assert 'x' in d
        assert 'w' not in d

    def test_attrdict_get(self):
        d = attrdict(x=10)
        assert d.get('x') == 10
        assert d.get('w') is None

    def test_attrdict_missing_attr_raises(self):
        d = attrdict(x=10)
        with pytest.raises(AttributeError):
            _ = d.missing

    def test_attrdict_missing_key_raises(self):
        d = attrdict(x=10)
        with pytest.raises(KeyError):
            _ = d['missing']

    def test_attrdict_del_attr(self):
        d = attrdict(x=10, y=20)
        del d.x
        assert 'x' not in d

    def test_attrdict_del_missing_attr_raises(self):
        d = attrdict(x=10)
        with pytest.raises(AttributeError):
            del d.missing

    def test_attrdict_set_abcmeta(self):

        # Create a class that is an instance of ABCMeta
        class MyAbstract(abc.ABC):
            pass

        d = attrdict()
        # Setting an ABCMeta instance attempts dict.__setattr__ which fails
        # because dict doesn't support arbitrary attributes
        with pytest.raises(AttributeError):
            d.AbstractClass = MyAbstract

    def test_attrdict_deepcopy(self):
        d = attrdict(x=10)
        tricky = [d]
        righty = copy.deepcopy(tricky)
        righty[0].x = 99
        assert d.x == 10


class TestLazydict:
    """Tests for lazydict class."""

    def test_lazydict_computed_value(self):
        a = lazydict(a=1, b=2, c=lambda x: x.a + x.b)
        assert a.c == 3

    def test_lazydict_recalculated(self):
        a = lazydict(a=1, b=2, c=lambda x: x.a + x.b)
        a.a = 99
        assert a.c == 101

    def test_lazydict_non_callable(self):
        a = lazydict(a=1, b=2)
        a.z = 1
        assert a.z == 1

    def test_lazydict_missing_attr_raises(self):
        a = lazydict(a=1)
        with pytest.raises(AttributeError):
            _ = a.missing


class TestEmptydict:
    """Tests for emptydict class."""

    def test_emptydict_missing_attr_returns_none(self):
        a = emptydict(a=1, b=2)
        assert a.c is None

    def test_emptydict_existing_attr(self):
        a = emptydict(a=1, b=2)
        assert a.b == 2

    def test_emptydict_get_item(self):
        a = emptydict(a=1, b=2)
        assert a['b'] == 2

    def test_emptydict_contains(self):
        a = emptydict(a=1, b=2)
        assert 'b' in a
        assert 'c' not in a

    def test_emptydict_get(self):
        a = emptydict(a=1, b=2)
        assert a.get('b') == 2
        assert a.get('c') is None


class TestBidict:
    """Tests for bidict class."""

    def test_bidict_basic(self):
        bd = bidict({'a': 1, 'b': 2})
        assert bd == {'a': 1, 'b': 2}
        assert bd.inverse == {1: ['a'], 2: ['b']}

    def test_bidict_multiple_keys_same_value(self):
        bd = bidict({'a': 1, 'b': 2})
        bd['c'] = 1
        assert bd.inverse[1] == ['a', 'c']

    def test_bidict_delete_updates_inverse(self):
        bd = bidict({'a': 1, 'b': 2, 'c': 1})
        del bd['c']
        assert bd.inverse[1] == ['a']

    def test_bidict_change_value_updates_inverse(self):
        bd = bidict({'a': 1, 'b': 2})
        bd['b'] = 3
        assert bd.inverse[2] == []
        assert bd.inverse[3] == ['b']

    def test_bidict_delete_clears_empty_inverse(self):
        bd = bidict({'a': 1})
        del bd['a']
        assert 1 not in bd.inverse


class TestMutableDict:
    """Tests for MutableDict class."""

    def test_mutabledict_insert_before(self):
        md = MutableDict({'a': 1, 'b': 2, 'c': 3})
        md.insert_before('b', 'x', 10)
        keys = list(md.keys())
        assert keys.index('x') < keys.index('b')

    def test_mutabledict_insert_after(self):
        md = MutableDict({'a': 1, 'b': 2, 'c': 3})
        md.insert_after('a', 'x', 10)
        keys = list(md.keys())
        assert keys.index('x') > keys.index('a')
        assert keys.index('x') < keys.index('b')

    def test_mutabledict_insert_after_last(self):
        md = MutableDict({'a': 1, 'b': 2})
        md.insert_after('b', 'c', 3)
        keys = list(md.keys())
        assert keys[-1] == 'c'


class TestCaseInsensitiveDict:
    """Tests for CaseInsensitiveDict class."""

    def test_case_insensitive_get(self):
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        assert cid['accept'] == 'application/json'
        assert cid['ACCEPT'] == 'application/json'

    def test_case_insensitive_set_overwrites(self):
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['ACCEPT'] = 'text/html'
        assert cid['accept'] == 'text/html'

    def test_case_insensitive_contains(self):
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        assert 'accept' in cid
        assert 'ACCEPT' in cid

    def test_case_insensitive_delete(self):
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        del cid['accept']
        assert 'Accept' not in cid

    def test_case_insensitive_len(self):
        cid = CaseInsensitiveDict()
        cid['a'] = 1
        cid['b'] = 2
        assert len(cid) == 2

    def test_case_insensitive_equality(self):
        cid1 = CaseInsensitiveDict({'a': 1, 'B': 2})
        cid2 = CaseInsensitiveDict({'A': 1, 'b': 2})
        assert cid1 == cid2

    def test_case_insensitive_copy(self):
        cid = CaseInsensitiveDict({'a': 1})
        cid2 = cid.copy()
        cid2['a'] = 99
        assert cid['a'] == 1

    def test_case_insensitive_eq_non_mapping(self):
        cid = CaseInsensitiveDict({'a': 1})
        # Equality with non-mapping returns False (NotImplemented handled by Python)
        assert (cid == [('a', 1)]) is False
        assert (cid == 'not a mapping') is False

    def test_case_insensitive_repr(self):
        cid = CaseInsensitiveDict({'a': 1, 'B': 2})
        result = repr(cid)
        assert 'a' in result
        assert '1' in result


if __name__ == '__main__':
    pytest.main([__file__])
