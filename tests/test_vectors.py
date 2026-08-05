"""Kernel assertions against the shared cross-language vectors.

Reads the same hand-derived tables in ``vectors/`` that
``rust/src/vectors.rs`` reads. Only ``numify`` has two implementations to
cross-check; ``parse`` and ``sanitize_vulgar_string`` reach the same
compiled kernel from both sides and merely share the oracle. See
``vectors/README.md`` for the case shape and the divergence convention.
"""
import json
import math
import pathlib

import pytest
from libb._rust import normalize_numeric_str
from libb.dicts import cmp
from libb.stats import numify, parse, safe_cmp
from libb.text import sanitize_vulgar_string

VECTORS = pathlib.Path(__file__).resolve().parent.parent / 'vectors'

SENTINELS = {'nan': math.nan, 'inf': math.inf, '-inf': -math.inf}

TARGETS = {'int': int, 'float': float}


def load(name):
    """Load a vector table, rejecting an empty one.

    A truncated or emptied file must not let a parametrized test pass by
    asserting nothing, so this raises rather than yielding no cases.
    """
    cases = json.loads((VECTORS / f'{name}.json').read_text(encoding='ascii'))
    if not cases:
        raise ValueError(f'{name}.json contains no cases')
    return cases


# Notes:
# - An empty DIVERGENT is the correct state once R4 closes, not a silent
#   gap. Removing a marker while the disagreement is still live reddens
#   rust/src/vectors.rs, which asserts the `rust` field on these rows.
DIVERGENT = [case for case in load('numify') if 'divergence' in case]


def resolve(expected):
    """Read an expected-value field, decoding the non-finite sentinels.
    """
    if isinstance(expected, str) and expected in SENTINELS:
        return SENTINELS[expected]
    return expected


def matches(got, want):
    """Compare a numeric result by value and type, treating NaN as equal.
    """
    if want is None:
        return got is None
    if isinstance(want, float) and math.isnan(want):
        return isinstance(got, float) and math.isnan(got)
    return got == want and type(got) is type(want)


@pytest.mark.parametrize(
    'case', load('normalize_numeric_str'), ids=lambda c: repr(c['input']))
def test_normalize_numeric_str_vectors(case):
    """Verify the shared normalizer against the vectors, via the Python export.

    This is the one kernel both bindings really share - stats.numify calls
    it - so a drift here moves Python and Rust together.

    Mutation: applying the accounting sign before the percent strip, so
        '(50%)' keeps its suffix and fails to coerce.
    Oracle: vectors/normalize_numeric_str.json, hand-derived and asserted
        against the Rust function directly by rust/src/vectors.rs.
    """
    got = normalize_numeric_str(case['input'])
    assert got == case['expected'], (
        f'normalize_numeric_str({case["input"]!r}): got {got!r}, '
        f'want {case["expected"]!r}')


@pytest.mark.parametrize('case', load('parse'), ids=lambda c: repr(c['input']))
def test_parse_vectors(case):
    """Verify parse() against the shared vectors, int/float type included.

    Mutation: returning a float where an all-digit string must yield an int,
        treating a comma as a decimal separator, or dropping the
        parentheses-as-negation branch.
    Oracle: vectors/parse.json, hand-derived from the documented
        semantics. parse() delegates to the Rust kernel, so this shares an
        oracle with rust/src/vectors.rs rather than cross-checking it.
    """
    want = resolve(case['expected'])
    got = parse(case['input'])
    assert matches(got, want), f'parse({case["input"]!r}): got {got!r}, want {want!r}'


@pytest.mark.parametrize(
    'case', load('numify'), ids=lambda c: f'{c["input"]!r}-{c["to"]}')
def test_numify_vectors(case):
    """Verify numify() against the shared vectors, int/float type included.

    Mutation: stripping the percent suffix before detecting the accounting
        parentheses, or coercing a fractional string with int() where the
        contract is to reject it.
    Oracle: vectors/numify.json, hand-derived from the documented
        semantics. This is the one table with two real implementations.
    """
    want = resolve(case['expected'])
    got = numify(case['input'], to=TARGETS[case['to']])
    assert matches(got, want), (
        f'numify({case["input"]!r}, to={case["to"]}): got {got!r}, want {want!r}')


def test_numify_divergence_markers_are_well_formed():
    """Verify the `rust` and `divergence` fields always appear together.

    rust/src/vectors.rs switches on `divergence` alone and then reads
    `rust`, so a row carrying one key without the other either drops back
    to the Python expectation or fails looking for a missing field.

    Mutation: mistyping either key on a pinned row, which empties the
        divergence set while the disagreement is still live.
    Oracle: the two key sets, each derived from the table independently.
    """
    rows = load('numify')
    marked = {(c['input'], c['to']) for c in rows if 'divergence' in c}
    valued = {(c['input'], c['to']) for c in rows if 'rust' in c}
    assert marked == valued, f'markers without values: {marked ^ valued}'


@pytest.mark.parametrize(
    'case', DIVERGENT, ids=lambda c: f'{c["input"]!r}-{c["to"]}')
def test_numify_divergences_still_diverge(case):
    """Verify Python still disagrees with each pinned Rust numify value.

    rust/src/vectors.rs asserts the `rust` field on these rows, so closing
    the R4 gap without deleting them would leave that side pinning a value
    the kernel no longer returns.

    Mutation: making stats.numify delegate to numparse::numify_str while
        leaving the pinned rows in place.
    Oracle: the live numify() result against the row's `rust` field.
    """
    got = numify(case['input'], to=TARGETS[case['to']])
    assert not matches(got, resolve(case['rust'])), (
        f'numify({case["input"]!r}, to={case["to"]}) now returns the pinned '
        f'Rust value; drop this row and its `rust`/`divergence` fields')


@pytest.mark.parametrize(
    'case', load('sanitize_vulgar_string'), ids=lambda c: repr(c['input']))
def test_sanitize_vulgar_string_vectors(case):
    """Verify sanitize_vulgar_string() against the shared vectors.

    Mutation: replacing matches left to right instead of in reverse, which
        shifts every later offset, dropping the offset-0 leading-space
        exception, or mistyping any of the 15 fraction table values.
    Oracle: vectors/sanitize_vulgar_string.json, one row per table entry.
        This function is imported straight from the extension, so the
        oracle is shared with rust/src/vectors.rs, not cross-checked.
    """
    assert sanitize_vulgar_string(case['input']) == case['expected']


@pytest.mark.parametrize(
    'case', load('cmp'), ids=lambda c: f'{c["left"]!r}-vs-{c["right"]!r}')
def test_cmp_vectors(case):
    """Verify cmp() against the shared vectors, including the iterable rules.

    Mutation: testing falsiness instead of None (which breaks 0 against
        None), or reaching element-wise comparison before the
        None-membership branches on iterable operands.
    Oracle: vectors/cmp.json, hand-derived from the documented semantics.
    """
    got = cmp(case['left'], case['right'])
    assert matches(got, case['expected']), (
        f'cmp({case["left"]!r}, {case["right"]!r}): got {got!r}, '
        f'want {case["expected"]!r}')


@pytest.mark.parametrize(
    'case', load('safe_cmp'), ids=lambda c: f'{c["a"]!r}{c["op"]}{c["b"]!r}')
def test_safe_cmp_vectors(case):
    """Verify safe_cmp() maps each operator onto the right cmp() outcomes.

    Mutation: an operator mapped to the wrong cmp() result set, such as
        '>=' accepting -1 or '<>' falling through to the operator call.
    Oracle: vectors/safe_cmp.json, hand-derived from the documented
        semantics.
    """
    got = safe_cmp(case['op'], case['a'], case['b'])
    assert matches(got, case['expected']), (
        f'safe_cmp({case["op"]!r}, {case["a"]!r}, {case["b"]!r}): '
        f'got {got!r}, want {case["expected"]!r}')
