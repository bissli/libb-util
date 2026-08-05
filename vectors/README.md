# Shared kernel test vectors

One checked-in table of `(input, args, expected)` per kernel, hand-derived
from the documented semantics rather than captured from a run, so that a new
implementation lands against a fixed oracle instead of against a reading of
the existing source:

| File                            | Consumed by                                    |
| ------------------------------- | ---------------------------------------------- |
| `normalize_numeric_str.json`    | `tests/test_vectors.py`, `rust/src/vectors.rs` |
| `parse.json`                    | `tests/test_vectors.py`, `rust/src/vectors.rs` |
| `numify.json`                   | `tests/test_vectors.py`, `rust/src/vectors.rs` |
| `sanitize_vulgar_string.json`   | `tests/test_vectors.py`, `rust/src/vectors.rs` |
| `cmp.json`                      | `tests/test_vectors.py`                        |
| `safe_cmp.json`                 | `tests/test_vectors.py`                        |

How much each table cross-checks matters, and it is not uniform:

- **`normalize_numeric_str.json` pins the one kernel both bindings really
  share.** `libb.stats.numify` calls it and so does `numify_str`, so the
  formatting rules - trim, `(x)`-as-negative, comma stripping, percent
  stripping - now have a single implementation and cannot drift.
- **`numify.json` is the table where the two sides still differ, by
  design.** They share the normaliser above but keep their own *coercion*
  policy: Python's `int()` rejects a fractional or exponent string and has
  arbitrary precision, while `numify_str` falls back to an `f64` parse and a
  saturating cast (see **Known divergences**).
- **`parse.json` and `sanitize_vulgar_string.json` reach the same compiled
  Rust from both sides.** `libb.stats.parse` delegates to the kernel and
  `libb.text.sanitize_vulgar_string` is imported straight from `libb._libb`,
  so the Python rows add only the PyO3 int/float conversion. Both sides
  share one oracle here; neither cross-checks a second implementation.
- **`cmp.json` and `safe_cmp.json` have no Rust side yet.** `libb.dicts.cmp`
  and `libb.stats.safe_cmp` are pure Python, so only the Python suite reads
  them. Their tables exist now so a future port lands against a fixed oracle.

## Case shape

Every file is a JSON array of objects.

- `normalize_numeric_str.json` - `input`, `expected` (a string, or null
  when nothing is left to convert)
- `parse.json` - `input`, `expected`
- `numify.json` - `input`, `to` (`"int"` or `"float"`), `expected`
- `sanitize_vulgar_string.json` - `input`, `expected`
- `cmp.json` - `left`, `right`, `expected`
- `safe_cmp.json` - `op`, `a`, `b`, `expected`
- `note` - optional prose, read by no test; states which defect the case
  catches, and for a fraction case, which fraction the escape denotes
- `rust`, `divergence` - **load-bearing, not informational**; see below

## Conventions

**Int against float.** A JSON number written without a decimal point is an
integer expectation; one written with a decimal point is a float expectation.
Both `json` (Python) and `serde_json` (Rust) preserve that distinction, and
both suites assert the type as well as the value, because `numify` returns
`int` or `float` depending on `to`, and because `True == 1` in Python.

**Non-finite floats.** JSON cannot express NaN or infinity, so in
`parse.json` and `numify.json` a *string* `expected` is a sentinel:
`"nan"`, `"inf"`, or `"-inf"`. Both readers decode sentinels in both files,
and `rust/src/vectors.rs` panics on an unrecognised one, so a string
`expected` there must be one of the three. `sanitize_vulgar_string.json`
and `normalize_numeric_str.json` treat a string `expected` as a real
result - their rows are strings by nature and bypass sentinel decoding
entirely.

**ASCII only.** Vulgar fraction characters are written as `\uXXXX` escapes
rather than raw UTF-8, so the files survive transfer paths that mangle high
bytes. Both JSON parsers decode the escapes identically, and the Python
loader reads with `encoding='ascii'` so a raw high byte fails loudly.
`sanitize_vulgar_string.json` carries one row per entry in the 15-value
fraction table in `rust/src/text.rs`, since a mistyped value or a dropped
key there is otherwise caught by nothing.

**Known divergences.** A case where the two `numify` implementations
genuinely disagree carries `rust` (what the Rust kernel returns today)
alongside `expected` (what the shipped Python API returns), plus a
`divergence` string naming the issue. `rust/src/vectors.rs` switches on the
presence of `divergence` and asserts `rust` on those rows, so a reader that
ignored these keys would fail. The two keys must always appear together;
`tests/test_vectors.py` asserts that.

The disagreement is pinned from both sides rather than hidden:
`test_numify_vectors` asserts the Python value and
`test_numify_divergences_still_diverge` asserts Python does *not* yet return
the pinned Rust value, so closing the gap reddens both and forces the rows
to be deleted. An empty set of divergence rows is the correct end state.

**Why the coercion divergence is kept rather than unified.** R4 proposed
either delegating `stats.numify` to `numify_str` or deleting the Rust copy.
Neither is available:

- Deleting the Rust side is impossible - `numify_str` is not a dormant twin,
  it is the body of `parse`, which is exported and is the consumer's
  hottest call.
- Delegating fully would change three shipped `numify(..., to=int)` results,
  and `libtc` depends on one of them. `tc/collection.py`'s
  `infer_numeric_type` uses `numify(v, int) is None` to decide a DataSet
  column is float rather than int, and its docstring names `'100.0'` and
  `'1e6'` explicitly. Delegating would type every float column as int and
  truncate on load.

So the duplication R4 is actually about - the formatting rules - is gone,
and the coercion policy stays deliberately per-language, pinned by the
divergence rows below rather than left to chance. `parse` is unaffected
either way: it has one implementation and routes through the Rust kernel.
