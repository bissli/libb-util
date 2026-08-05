"""Python-only contracts for numify, cmp, and safe_cmp.

These behaviours cannot go in ``vectors/`` - a JSON table cannot express a
callable operator, an arbitrary object, or a raised exception - so they are
asserted here instead of being left uncovered. Everything expressible as
data lives in the shared tables; see ``vectors/README.md``.
"""
import math
import operator

import pytest
from libb.dicts import cmp
from libb.stats import numify, safe_cmp


def test_numify_passes_through_non_string_input():
    """Verify numify's non-string branches keep their coercion contract.

    The shared vectors only carry string inputs, because the Rust kernel
    takes &str. These branches are Python-only and are what libtc calls
    with already-typed spreadsheet cells.

    Mutation: normalizing before the isinstance checks, which would make
        numify(None) raise instead of returning None, or routing an int
        through the string path.
    Oracle: hand-computed - truncation toward zero for 2.7, widening for 3,
        and None for a value int() cannot accept.
    """
    assert numify(None, to=float) is None
    assert numify(2.7, to=int) == 2
    assert numify(2.7, to=float) == 2.7
    assert numify(3, to=float) == 3.0
    assert type(numify(3, to=float)) is float
    assert numify(math.nan, to=int) is None
    assert numify(math.inf, to=int) is None
    assert numify(object(), to=float) is None


def test_numify_rejects_fractional_int_coercion():
    """Verify numify(v, int) still returns None for a non-integer string.

    libtc's DataSet type inference (tc/collection.py infer_numeric_type)
    reads None here as "not an int column, try float". If these ever
    coerced, every float column in a DataSet would be typed int and then
    truncate on load.

    Mutation: making stats.numify delegate its coercion to the Rust
        numify_str, whose int path falls back to an f64 parse and truncates.
    Oracle: Python's int() contract, which raises on both forms; the two
        cases named in infer_numeric_type's own docstring.
    """
    assert numify('100.0', to=int) is None
    assert numify('1e6', to=int) is None
    assert numify('100.0', to=float) == 100.0
    assert numify('1e6', to=float) == 1000000.0


def test_numify_int_keeps_arbitrary_precision():
    """Verify numify(v, int) does not clamp a value wider than i64.

    Mutation: routing the int coercion through the Rust kernel, whose
        f64 -> i64 cast saturates at i64::MAX.
    Oracle: the exact decimal 2**63, which is one above i64::MAX.
    """
    assert numify('9223372036854775808', to=int) == 2 ** 63
    assert numify('9223372036854775808', to=int) != 2 ** 63 - 1


@pytest.mark.parametrize(('op', 'expected'), [
    (operator.gt, False),
    (operator.ge, False),
    (operator.lt, True),
    (operator.le, True),
    (operator.eq, False),
    (operator.ne, True),
    ])
def test_safe_cmp_accepts_operator_callables(op, expected):
    """Verify each operator function maps to the same outcome as its string.

    safe_cmp matches on ``op in {'>', operator.gt}``, so the callable forms
    share a branch with the strings but are unreachable from a JSON table.

    Mutation: dropping a callable from one of those set literals, which
        silently falls through to ``op(a, b)`` and raises TypeError on None.
    Oracle: None orders before any value, so lt/le/ne hold and the rest
        do not.
    """
    assert safe_cmp(op, None, 1) is expected


def test_safe_cmp_falls_through_to_an_unknown_callable():
    """Verify an operator outside the known set is called directly.

    Mutation: returning False or raising for an unrecognised op instead of
        delegating, which would silently break a caller passing a custom
        predicate.
    Oracle: a sentinel-returning callable, proving delegation happened
        rather than any built-in branch.
    """
    assert safe_cmp(lambda a, b: 'delegated', None, 1) == 'delegated'


def test_safe_cmp_rejects_an_unknown_operator_string():
    """Verify an unrecognised operator string is not silently accepted.

    An unknown string reaches the ``op(a, b)`` fallthrough and is not
    callable, so it raises rather than comparing wrongly.

    Mutation: adding a catch-all that returns False, turning a typo'd
        operator into a silently wrong comparison.
    Oracle: str is not callable, so TypeError is the only correct outcome.
    """
    with pytest.raises(TypeError):
        safe_cmp('=>', 1, 2)


def test_cmp_orders_an_iterable_against_none():
    """Verify a scalar None still orders before an iterable operand.

    Mutation: reaching the iterable branch for a None operand, where
        ``iter(None)`` raises and the scalar rules must take over.
    Oracle: the documented rule that None precedes any value, applied with
        a list on the other side.
    """
    assert cmp([1], None) == 1
    assert cmp(None, [1]) == -1


def test_cmp_raises_on_incomparable_mixed_operands():
    """Verify cmp does not invent an order for a scalar against a sequence.

    The final ``_cmp`` sits outside the try, so a TypeError from Python's
    own comparison propagates rather than being swallowed into a 0.

    Mutation: wrapping the scalar comparison in the same try/except, which
        would turn every incomparable pair into "equal" and corrupt a sort.
    Oracle: Python's own '>' contract between int and list.
    """
    for left, right in [(1, [1]), ('abc', [1]), ({1: 2}, {3: 4})]:
        with pytest.raises(TypeError):
            cmp(left, right)


def test_cmp_does_not_silently_misorder_consumed_iterators():
    """Verify cmp raises on bare iterators rather than comparing them wrongly.

    ``None in it`` consumes the iterator, so by the time the element-wise
    comparison runs both operands are exhausted. Raising is the safe
    outcome; returning 0 would silently call every pair of iterators equal.

    Mutation: adding an iterator fallback that compares the exhausted
        remainders, which reports equality for any two iterators.
    Oracle: list_iterator has no ordering, so TypeError is what escapes.
    """
    with pytest.raises(TypeError):
        cmp(iter([1, 2]), iter([3, 4]))


def test_cmp_applies_the_none_rule_to_sets():
    """Verify the iterable None rule is membership-based, not order-based.

    Mutation: implementing the iterable branch by indexing or slicing,
        which fails on a set even though membership is well defined.
    Oracle: a set containing None against one that does not.
    """
    assert cmp({1, None}, {2}) == -1
    assert cmp({2}, {1, None}) == 1
