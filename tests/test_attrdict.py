import abc
import copy

import pytest

from libb import CaseInsensitiveDict, MutableDict, attrdict, bidict, emptydict
from libb import lazydict


class TestAttrdict:
    """Tests for attrdict class."""

    def test_attrdict_get_attr(self):
        """Verify attribute reads resolve against the live mapping.

        Mutation: __getattr__ caching the value, or reading the instance
            attribute namespace instead of the mapping.
        Oracle: a value written straight through dict.__setitem__, which
            bypasses every attrdict code path.
        """
        d = attrdict(x=10, y='foo')
        assert d.x == 10
        assert d.y == 'foo'
        dict.__setitem__(d, 'x', 11)  # noqa: PLC2801
        assert d.x == 11

    def test_attrdict_get_item_prefers_key_over_attribute(self):
        """Verify a stored key wins over a same-named method.

        Mutation: __getitem__ testing _MAPPING_API before
            dict.__getitem__, which would hide a stored 'keys' behind the
            KeyError meant for the method.
        Oracle: hand-computed - 'keys' names both a method and a stored
            key, and only the stored value is correct.
        """
        d = attrdict(x=10, keys='shadowed')
        assert d['x'] == 10
        assert d['keys'] == 'shadowed'

    def test_attrdict_contains_agrees_with_getitem_on_method_names(self):
        """Verify `in`, [] and get() answer alike for a method name.

        Mutation: dropping the _MAPPING_API guard in __getitem__, which
            answers 'keys' with a bound method while `in` still says no.
        Oracle: the three access paths against each other, plus the
            caller's own default of 0 rather than a truthy method.
        """
        d = attrdict(x=10)
        assert 'x' in d
        assert 'w' not in d

        assert 'keys' not in d
        with pytest.raises(KeyError):
            d['keys']
        assert d.get('keys', 0) == 0

    def test_attrdict_subclass_surface_stays_reachable(self):
        """Verify everything a subclass declares reads as a key.

        The guard names only this class's own methods, so a subclass owns
        the rest of the name space.

        Mutation: guarding on `callable(attr)` or on dir(type(self))
            instead of _MAPPING_API, either of which also swallows the
            subclass's own method or its whole attribute surface.
        Oracle: 1 from the property, 5 from the class attribute, and a
            callable for the declared method, against the KeyError the
            same lookup gives for 'keys'.
        """

        class Declaring(attrdict):
            __slots__ = ()

            LIMIT = 5

            @property
            def scaled(self):
                return 1

            def helper(self):
                return 'mine'

        d = Declaring(a=1)
        assert d['scaled'] == d.scaled == d.get('scaled') == 1
        assert d['LIMIT'] == 5
        assert callable(d['helper'])
        with pytest.raises(KeyError):
            d['keys']

    def test_attrdict_get(self):
        """Verify get() returns the caller's default on a miss.

        Mutation: returning a bare None instead of `default`, or
            swallowing the default argument.
        Oracle: hand-computed sentinel that cannot be confused with None.
        """
        d = attrdict(x=10)
        assert d.get('x') == 10
        assert d.get('w') is None
        assert d.get('w', 'fallback') == 'fallback'

    def test_attrdict_get_routes_through_getitem(self):
        """Verify get() and [] and . agree on a property-backed name.

        Mutation: get() calling dict.__getitem__ directly, or __getitem__
            dropping its attribute fallback, either of which strands the
            property behind a KeyError.
        Oracle: the property's own return value, 1, reached three ways.
        """

        class WithProperty(attrdict):
            __slots__ = ()

            @property
            def x(self):
                return 1

        a = WithProperty()
        assert a['x'] == 1
        assert a.x == 1
        assert a.get('x') == 1

    def test_attrdict_missing_hook_is_honored(self):
        """Verify a subclass __missing__ fires on all three access forms.

        Mutation: guarding the fetch with `in` before calling
            dict.__getitem__, which skips __missing__ and raises.
        Oracle: hand-computed 'made:zz', a value only __missing__ can
            produce, reached through item, attribute, and get access.
        """

        class Defaulting(attrdict):
            __slots__ = ()

            def __missing__(self, key):
                return f'made:{key}'

        d = Defaulting(a=1)
        assert d['zz'] == 'made:zz'
        assert d.zz == 'made:zz'
        assert d.get('zz') == 'made:zz'
        assert d['a'] == 1

    def test_attrdict_attribute_access_bypasses_subclass_getitem(self):
        """Verify attribute reads take the mapping, not a subclass hook.

        Mutation: routing __getattr__ through self[attrname] to make the
            three forms agree, which re-enters __getitem__'s attribute
            fallback and recurses without bound on any absent name.
        Oracle: the same key read both ways - 100 through the override,
            1 straight from the mapping.
        """

        class Doubling(attrdict):
            __slots__ = ()

            def __getitem__(self, attrname):
                return attrdict.__getitem__(self, attrname) * 100

        d = Doubling(a=1)
        assert d['a'] == 100
        assert d.get('a') == 100
        assert d.a == 1
        with pytest.raises(AttributeError):
            _ = d.absent

    def test_attrdict_attribute_hit_takes_no_python_level_lookup(self):
        """Verify an attribute hit reaches the mapping in one step.

        Mutation: reinstating an `in` guard or a self[attrname] fetch in
            either __getattr__, each of which turns one C-level lookup
            on the hot path into two or three Python-level calls.
        Oracle: spies on __contains__ and __getitem__, which the hit
            path must not reach at all.
        """
        calls = []

        class CountingAttr(attrdict):
            __slots__ = ()

            def __contains__(self, key):
                calls.append('contains')
                return dict.__contains__(self, key)

            def __getitem__(self, key):
                calls.append('getitem')
                return attrdict.__getitem__(self, key)

        class CountingLazy(lazydict):
            __slots__ = ()

            def __contains__(self, key):
                calls.append('contains')
                return dict.__contains__(self, key)

            def __getitem__(self, key):
                calls.append('getitem')
                return lazydict.__getitem__(self, key)

        assert CountingAttr(x=10).x == 10
        assert calls == []
        assert CountingLazy(x=10).x == 10
        assert calls == []

    def test_attrdict_set_attr(self):
        """Verify attribute writes land in the mapping.

        Mutation: __setattr__ routing an ordinary value to
            dict.__setattr__ instead of __setitem__.
        Oracle: the value read back through the item path.
        """
        d = attrdict(x=10, y='foo')
        d.y = 'baa'
        assert d['y'] == 'baa'

    def test_attrdict_copy(self):
        """Verify copy() returns an independent attrdict.

        Mutation: copy() returning self, or update() returning None so
            the copy is discarded.
        Oracle: mutating the copy must leave the original at 10.
        """
        d = attrdict(x=10)
        g = d.copy()
        g.x = 11
        assert d.x == 10
        assert g.x == 11

    def test_attrdict_missing_attr_raises(self):
        """Verify a missing attribute raises AttributeError, not KeyError.

        Mutation: letting the underlying KeyError escape, or returning
            None for an absent name.
        Oracle: the exception type itself, plus the offending name.
        """
        d = attrdict(x=10)
        with pytest.raises(AttributeError) as excinfo:
            _ = d.missing
        assert excinfo.value.args[0] == 'missing'

    def test_attrdict_missing_attr_suppresses_key_error_context(self):
        """Verify the AttributeError hides the KeyError that caused it.

        Mutation: dropping `from None`, which reinstates the "During
            handling of the above exception" chain in every traceback.
        Oracle: __suppress_context__, set only by a `from None` raise.
        """
        d = attrdict(x=10)
        with pytest.raises(AttributeError) as excinfo:
            _ = d.missing
        assert excinfo.value.__suppress_context__ is True
        assert excinfo.value.__cause__ is None

    def test_attrdict_missing_key_raises(self):
        """Verify a missing key raises KeyError once both paths fail.

        Mutation: returning None after the attribute fallback misses, or
            letting that fallback's AttributeError escape as-is.
        Oracle: the exception type, which must survive the fallback.
        """
        d = attrdict(x=10)
        with pytest.raises(KeyError) as excinfo:
            _ = d['missing']
        assert excinfo.value.args[0] == 'missing'

    def test_attrdict_del_attr(self):
        """Verify del removes the key from the mapping.

        Mutation: a flipped membership guard, or a __delattr__ that
            raises correctly but never pops.
        Oracle: membership and length after the delete.
        """
        d = attrdict(x=10, y=20)
        del d.x
        assert 'x' not in d
        assert len(d) == 1

    def test_attrdict_del_missing_attr_raises(self):
        """Verify deleting an absent attribute raises AttributeError.

        Mutation: letting pop's KeyError escape unconverted, or dropping
            `from None` so the traceback carries the KeyError chain.
        Oracle: the exception type and name, plus __suppress_context__,
            which only a `from None` raise sets.
        """
        d = attrdict(x=10)
        with pytest.raises(AttributeError) as excinfo:
            del d.missing
        assert excinfo.value.args[0] == 'missing'
        assert excinfo.value.__suppress_context__ is True

    def test_attrdict_del_attr_honors_subclass_pop(self):
        """Verify deletion routes through pop, so a subclass sees it.

        Mutation: calling dict.pop(self, attrname) instead, which skips
            a subclass override the way attribute reads already do.
        Oracle: a spy pop recording the key it was handed.
        """
        popped = []

        class Logging(attrdict):
            __slots__ = ()

            def pop(self, key, *args):
                popped.append(key)
                return dict.pop(self, key, *args)

        d = Logging(x=10, y=20)
        del d.x
        assert popped == ['x']
        assert 'x' not in d
        assert d.y == 20

    def test_attrdict_set_abcmeta(self):
        """Verify an ABCMeta value takes the attribute path and fails.

        Mutation: a flipped isinstance guard, which would store the class
            as an ordinary key and never raise.
        Oracle: dict rejects arbitrary instance attributes, so the
            attribute path is observable as an AttributeError.
        """

        class MyAbstract(abc.ABC):
            pass

        d = attrdict()
        with pytest.raises(AttributeError):
            d.AbstractClass = MyAbstract
        assert 'AbstractClass' not in d

    def test_attrdict_deepcopy(self):
        """Verify deepcopy produces a fully detached attrdict.

        Mutation: __getattr__ answering dunder probes such as
            __deepcopy__ with a value instead of raising AttributeError.
        Oracle: mutating the copy must leave the original at 10.
        """
        d = attrdict(x=10)
        tricky = [d]
        righty = copy.deepcopy(tricky)
        righty[0].x = 99
        assert d.x == 10

    def test_attrdict_fromkeys(self):
        """Verify fromkeys returns an attrdict, not a plain dict.

        Mutation: delegating to dict.fromkeys and returning its result.
        Oracle: isinstance plus attribute access, which a plain dict
            cannot answer.
        """
        d = attrdict.fromkeys(['a', 'b'], 0)
        assert isinstance(d, attrdict)
        assert d.a == 0
        assert d.b == 0

    def test_attrdict_or(self):
        """Verify | returns an attrdict and the right operand wins.

        Mutation: returning dict.__or__'s plain dict, or swapping the
            operands so the left side wins the collision.
        Oracle: hand-computed - x is 2 because the right operand is last.
        """
        d = attrdict(x=1) | {'x': 2, 'y': 3}
        assert isinstance(d, attrdict)
        assert d.x == 2
        assert d.y == 3

    def test_attrdict_ror(self):
        """Verify reverse | keeps attrdict on the right as the winner.

        Mutation: implementing __ror__ with dict.__or__, which swaps the
            operands and lets the plain dict win the collision.
        Oracle: hand-computed - x is 1, the attrdict's value, not 99.
        """
        d = {'x': 99, 'y': 2} | attrdict(x=1)
        assert isinstance(d, attrdict)
        assert d.x == 1
        assert d.y == 2

    def test_attrdict_ior(self):
        """Verify |= mutates in place and keeps the attrdict type.

        Mutation: __ior__ returning None, which rebinds the name to None.
        Oracle: identity against the pre-merge object.
        """
        d = attrdict(x=1)
        original = d
        d |= {'y': 2}
        assert isinstance(d, attrdict)
        assert d is original
        assert d.x == 1
        assert d.y == 2


class TestLazydict:
    """Tests for lazydict class."""

    def test_lazydict_computed_value(self):
        """Verify a callable value is called with the dict as argument.

        Mutation: a flipped callable() guard, or calling with no
            argument so the lambda cannot reach its siblings.
        Oracle: hand-computed 1 + 2 == 3.
        """
        a = lazydict(a=1, b=2, c=lambda x: x.a + x.b)
        assert a.c == 3

    def test_lazydict_recalculated_not_cached(self):
        """Verify each read re-evaluates instead of caching the result.

        Mutation: storing the computed value back into the mapping, so
            the first read freezes the answer.
        Oracle: hand-computed 3 before the write and 101 after it, read
            in that order so a cache would return the stale 3.
        """
        a = lazydict(a=1, b=2, c=lambda x: x.a + x.b)
        assert a.c == 3
        a.a = 99
        assert a.c == 101

    def test_lazydict_non_callable(self):
        """Verify a plain value is returned untouched, not invoked.

        Mutation: a flipped callable() guard, which would try to call an
            int and raise TypeError.
        Oracle: the stored value itself.
        """
        a = lazydict(a=1, b=2)
        a.z = 1
        assert a.z == 1

    def test_lazydict_missing_attr_raises(self):
        """Verify a missing attribute raises AttributeError, not KeyError.

        Mutation: letting the underlying KeyError escape unconverted.
        Oracle: the exception type on a name known to be absent.
        """
        a = lazydict(a=1)
        with pytest.raises(AttributeError):
            _ = a.missing

    def test_lazydict_item_access_returns_raw_callable(self):
        """Verify [] returns the function while . evaluates it.

        Mutation: moving the callable() evaluation into __getitem__, so
            both paths evaluate and the function becomes unreachable.
        Oracle: the stored lambda's identity against d['c'].
        """
        def add_one(mapping):
            return mapping.a + 1

        a = lazydict(a=1, c=add_one)
        assert a['c'] is add_one
        assert a.c == 2

    def test_lazydict_copy_keeps_resolving(self):
        """Verify copy() returns a lazydict, not a downgraded attrdict.

        Mutation: copying into attrdict(...) rather than type(self), which
            leaves the copy holding the raw function forever.
        Oracle: the copy resolves to the same 3 the original does, and
            reflects a later edit to its own operand.
        """
        a = lazydict(a=1, b=2, c=lambda x: x.a + x.b)
        cp = a.copy()
        assert type(cp) is lazydict
        assert cp.c == a.c == 3
        cp.a = 99
        assert cp.c == 101

    def test_lazydict_or_keeps_resolving(self):
        """Verify | and reverse | both return a lazydict.

        Mutation: merging into attrdict(...) rather than type(self), so a
            merged row stops resolving its computed columns.
        Oracle: c resolves to 30 on both operand orders, against the
            hand-computed 10 + 20.
        """
        a = lazydict(a=10, c=lambda x: x.a + x.b)
        assert (a | {'b': 20}).c == 30
        assert ({'b': 20} | a).c == 30

    def test_lazydict_copy_is_independent(self):
        """Verify a copy shares no storage with the original.

        Mutation: returning self from copy(), or dropping update()'s
            return so the kwargs overrides are discarded.
        Oracle: the original keeps 1 after the copy moves to 11, and the
            kwargs override lands only on the copy.
        """
        a = lazydict(a=1)
        cp = a.copy(a=11)
        assert a.a == 1
        assert cp.a == 11


class TestEmptydict:
    """Tests for emptydict class."""

    def test_emptydict_missing_attr_returns_none(self):
        """Verify an absent attribute yields None instead of raising.

        Mutation: dropping the except clause so attrdict's
            AttributeError propagates.
        Oracle: None, on a name known to be absent.
        """
        a = emptydict(a=1, b=2)
        assert a.c is None

    def test_emptydict_missing_item_returns_none(self):
        """Verify an absent key yields None instead of raising KeyError.

        Mutation: catching AttributeError rather than KeyError in
            emptydict.__getitem__, which leaves attrdict's KeyError to
            escape.
        Oracle: None, on a key known to be absent.
        """
        a = emptydict(a=1, b=2)
        assert a['c'] is None

    def test_emptydict_preserves_falsy_values(self):
        """Verify a stored falsy value is returned, not turned into None.

        Mutation: collapsing the lookup to `value or None`, which cannot
            tell a stored 0 or '' from an absent key.
        Oracle: hand-computed - 0 and '' are present, 'nope' is not.
        """
        a = emptydict(zero=0, blank='')
        assert a['zero'] == 0
        assert a.blank == ''  # noqa: PLC1901
        assert a['nope'] is None

    def test_emptydict_contains_stays_honest(self):
        """Verify `in` reports real membership despite the None getters.

        Mutation: __contains__ defined in terms of __getitem__, which on
            emptydict never raises and so would report every name
            present.
        Oracle: 'c' is absent even though a['c'] and hasattr both answer.
        """
        a = emptydict(a=1, b=2)
        assert 'b' in a
        assert 'c' not in a
        assert a['c'] is None
        assert hasattr(a, 'c')

    def test_emptydict_method_name_reads_as_absent(self):
        """Verify a method name reads as None, honoring this class's rule.

        Mutation: dropping the _MAPPING_API guard in attrdict, which
            answers 'keys' with a bound method and so breaks the "None
            for a non-existing key" contract.
        Oracle: None for the method name, against the 3 a stored key of
            the same name returns.
        """
        a = emptydict(a=1)
        assert a['keys'] is None
        assert a.get('keys') is None
        assert emptydict(keys=3)['keys'] == 3

    def test_emptydict_get(self):
        """Verify get() still honors a caller-supplied default.

        Mutation: get() short-circuiting to None because __getitem__ no
            longer raises the KeyError it keys off.
        Oracle: hand-computed sentinel distinct from None.
        """
        a = emptydict(a=1, b=2)
        assert a.get('b') == 2
        assert a.get('c') is None
        assert a.get('c', 'fallback') is None


class TestBidict:
    """Tests for bidict class."""

    def test_bidict_basic(self):
        """Verify the inverse map is built during __init__.

        Mutation: skipping the seeding loop, leaving inverse empty.
        Oracle: hand-computed inverse of a two-item mapping.
        """
        bd = bidict({'a': 1, 'b': 2})
        assert bd == {'a': 1, 'b': 2}
        assert bd.inverse == {1: ['a'], 2: ['b']}

    def test_bidict_multiple_keys_same_value(self):
        """Verify a repeated value accumulates keys in insertion order.

        Mutation: overwriting the inverse entry instead of appending, or
            appending in reverse.
        Oracle: hand-computed ['a', 'c'], ordered by insertion.
        """
        bd = bidict({'a': 1, 'b': 2})
        bd['c'] = 1
        assert bd.inverse[1] == ['a', 'c']

    def test_bidict_delete_updates_inverse(self):
        """Verify deleting a key drops it from the inverse entry.

        Mutation: __delitem__ removing from the mapping but not the
            inverse.
        Oracle: hand-computed ['a'] after removing the second key of two.
        """
        bd = bidict({'a': 1, 'b': 2, 'c': 1})
        del bd['c']
        assert bd.inverse[1] == ['a']

    def test_bidict_change_value_updates_inverse(self):
        """Verify reassigning a value unhooks the key from the old one.

        Mutation: __setitem__ appending to the new value without
            removing the key from its previous value's list.
        Oracle: hand-computed - the old entry is emptied, not left as
            ['b'].
        """
        bd = bidict({'a': 1, 'b': 2})
        bd['b'] = 3
        assert bd.inverse[2] == []
        assert bd.inverse[3] == ['b']

    def test_bidict_delete_clears_empty_inverse(self):
        """Verify the last key's removal drops the inverse entry itself.

        Mutation: leaving the emptied list in place rather than deleting
            the key from inverse.
        Oracle: membership of the value in inverse, not its list length.
        """
        bd = bidict({'a': 1})
        del bd['a']
        assert 1 not in bd.inverse


class TestMutableDict:
    """Tests for MutableDict class."""

    def test_mutabledict_insert_before(self):
        """Verify insert_before lands ahead of the anchor key.

        Mutation: an off-by-one on the insertion index, which places the
            new key after the anchor instead.
        Oracle: hand-computed ['a', 'x', 'b', 'c'] key order.
        """
        md = MutableDict({'a': 1, 'b': 2, 'c': 3})
        md.insert_before('b', 'x', 10)
        assert list(md.keys()) == ['a', 'x', 'b', 'c']
        assert md['x'] == 10

    def test_mutabledict_insert_after(self):
        """Verify insert_after lands between the anchor and its successor.

        Mutation: an off-by-one on the insertion index, which places the
            new key before the anchor instead.
        Oracle: hand-computed ['a', 'x', 'b', 'c'] key order.
        """
        md = MutableDict({'a': 1, 'b': 2, 'c': 3})
        md.insert_after('a', 'x', 10)
        assert list(md.keys()) == ['a', 'x', 'b', 'c']
        assert md['x'] == 10

    def test_mutabledict_insert_after_last(self):
        """Verify appending past the final key carries the value along.

        Mutation: the trailing-key branch storing a placeholder instead
            of val, which the key-order assertion alone cannot see.
        Oracle: hand-computed key order plus the value itself.
        """
        md = MutableDict({'a': 1, 'b': 2})
        md.insert_after('b', 'c', 3)
        assert list(md.keys()) == ['a', 'b', 'c']
        assert md['c'] == 3


class TestCaseInsensitiveDict:
    """Tests for CaseInsensitiveDict class."""

    def test_case_insensitive_get(self):
        """Verify lookup folds case on both the stored and queried key.

        Mutation: storing under the raw key, so only the original casing
            resolves.
        Oracle: the same value reached through three different casings.
        """
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        assert cid['accept'] == 'application/json'
        assert cid['ACCEPT'] == 'application/json'

    def test_case_insensitive_set_overwrites(self):
        """Verify a differently cased write replaces the same entry.

        Mutation: storing under the raw key, which would leave two
            independent entries.
        Oracle: the second value wins, and length stays at one.
        """
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['ACCEPT'] = 'text/html'
        assert cid['accept'] == 'text/html'
        assert len(cid) == 1

    def test_case_insensitive_contains(self):
        """Verify membership testing folds case.

        Mutation: storing under the raw key, so only the original casing
            reports present.
        Oracle: two casings neither of which was the one written.
        """
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        assert 'accept' in cid
        assert 'ACCEPT' in cid

    def test_case_insensitive_delete(self):
        """Verify a differently cased delete removes the entry.

        Mutation: deleting under the raw key rather than the folded one.
        Oracle: a casing that matches neither the stored key nor its
            folded form, so only a folding delete can find it.
        """
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        del cid['ACCEPT']
        assert 'Accept' not in cid
        assert len(cid) == 0

    def test_case_insensitive_len_folds_case(self):
        """Verify length counts case-folded entries, not raw writes.

        Mutation: keying _store on the raw key, which counts 'A' and 'a'
            as two entries.
        Oracle: hand-computed - two writes differing only in case are
            one entry.
        """
        cid = CaseInsensitiveDict()
        cid['A'] = 1
        cid['a'] = 2
        assert len(cid) == 1
        assert cid['A'] == 2

    def test_case_insensitive_iter_yields_original_casing(self):
        """Verify iteration returns the last casing written, not lowered.

        Mutation: iterating _store's folded keys instead of the stored
            cased keys, which silently lowercases every header name.
        Oracle: hand-computed ['Accept'], the casing as written.
        """
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        assert list(cid) == ['Accept']
        assert list(cid.keys()) == ['Accept']

    def test_case_insensitive_lower_items(self):
        """Verify lower_items pairs folded keys with values, not keys.

        Mutation: emitting the stored cased key in the value slot.
        Oracle: hand-computed [('content-type', 'application/json')].
        """
        cid = CaseInsensitiveDict({'Content-Type': 'application/json'})
        assert list(cid.lower_items()) == [('content-type', 'application/json')]

    def test_case_insensitive_equality(self):
        """Verify equality folds case on both sides.

        Mutation: comparing cased keys, which would call these unequal.
        Oracle: two mappings differing only in the casing of their keys.
        """
        cid1 = CaseInsensitiveDict({'a': 1, 'B': 2})
        cid2 = CaseInsensitiveDict({'A': 1, 'b': 2})
        assert cid1 == cid2

    def test_case_insensitive_copy(self):
        """Verify copy() returns an independent store.

        Mutation: returning self, so writes to the copy hit the
            original.
        Oracle: the original's value after mutating the copy.
        """
        cid = CaseInsensitiveDict({'a': 1})
        cid2 = cid.copy()
        cid2['a'] = 99
        assert cid['a'] == 1

    def test_case_insensitive_eq_non_mapping_defers(self):
        """Verify comparing to a non-mapping defers to the other operand.

        Mutation: returning False instead of NotImplemented, which
            denies the right operand its reflected __eq__ and silently
            changes the answer.
        Oracle: a spy whose __eq__ returns True, reachable only if
            NotImplemented was returned.
        """

        class AlwaysEqual:  # noqa: PLW1641
            def __eq__(self, other):
                return True

        cid = CaseInsensitiveDict({'a': 1})
        assert (cid == AlwaysEqual()) is True
        assert (cid == [('a', 1)]) is False
        assert (cid == 'not a mapping') is False

    def test_case_insensitive_repr(self):
        """Verify repr renders the cased keys and their values.

        Mutation: rendering the folded store, which would lose the
            original casing.
        Oracle: the exact rendering of a single-entry mapping.
        """
        cid = CaseInsensitiveDict({'Accept': 1})
        assert repr(cid) == "{'Accept': 1}"


if __name__ == '__main__':
    pytest.main([__file__])
