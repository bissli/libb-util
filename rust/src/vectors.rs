//! Kernel assertions against the shared cross-language vectors.
//!
//! Reads the same hand-derived tables in `vectors/` that
//! `tests/test_vectors.py` reads. `normalize_numeric_str` is genuinely shared
//! with `libb.stats.numify`, and `numify_str` is the one kernel with a second
//! implementation to cross-check; `parse` and `sanitize_vulgar_string` are
//! reached from both sides as the same compiled code, so there the tables
//! guard against regression rather than drift. See `vectors/README.md` for the
//! case shape and the divergence convention.

use serde_json::Value;

use crate::numparse::{self, ParsedNumber, TargetType};
use crate::text;

const NORMALIZE_VECTORS: &str = include_str!("../../vectors/normalize_numeric_str.json");
const PARSE_VECTORS: &str = include_str!("../../vectors/parse.json");
const NUMIFY_VECTORS: &str = include_str!("../../vectors/numify.json");
const SANITIZE_VECTORS: &str = include_str!("../../vectors/sanitize_vulgar_string.json");

/// Read a vector's expected-value field as a `ParsedNumber`.
///
/// A JSON string is a non-finite sentinel; a JSON number carrying a decimal
/// point is a float expectation and one without is an int expectation.
fn expected_number(field: &Value) -> ParsedNumber {
    match field {
        Value::Null => ParsedNumber::None,
        Value::String(sentinel) => match sentinel.as_str() {
            "nan" => ParsedNumber::Float(f64::NAN),
            "inf" => ParsedNumber::Float(f64::INFINITY),
            "-inf" => ParsedNumber::Float(f64::NEG_INFINITY),
            other => panic!("unknown non-finite sentinel {other:?}"),
        },
        Value::Number(n) if n.is_f64() => ParsedNumber::Float(n.as_f64().unwrap()),
        // An int expectation outside i64 is only reachable on a divergence
        // row, whose Python side has arbitrary precision; surface it as a
        // mismatch against the kernel's saturated value rather than a panic.
        Value::Number(n) => match n.as_i64() {
            Some(i) => ParsedNumber::Int(i),
            None => ParsedNumber::Float(n.as_f64().expect("number must be representable")),
        },
        other => panic!("unsupported expected value {other}"),
    }
}

/// Compare two results, treating a pair of NaN floats as a match.
fn numbers_match(got: &ParsedNumber, want: &ParsedNumber) -> bool {
    match (got, want) {
        (ParsedNumber::Float(a), ParsedNumber::Float(b)) if a.is_nan() && b.is_nan() => true,
        _ => got == want,
    }
}

/// Load a vector table, rejecting an empty one so a truncated file cannot
/// make a test pass by asserting nothing.
fn load(table: &str, name: &str) -> Vec<Value> {
    let cases: Vec<Value> = serde_json::from_str(table).unwrap_or_else(|e| panic!("{name}: {e}"));
    assert!(!cases.is_empty(), "{name} contains no cases");
    cases
}

/// Verify `numparse::normalize_numeric_str` against the shared vectors.
///
/// This is the one kernel both bindings genuinely share: `libb.stats.numify`
/// calls it too, so a drift here changes Python and Rust together instead of
/// silently splitting them.
///
/// Mutation: applying the accounting sign before the percent strip (so
///   `(50%)` keeps its suffix), stripping every trailing `%` rather than
///   one, filtering interior whitespace as if it were a separator, or
///   dropping the re-trim of the unwrapped parenthesised text.
/// Oracle: vectors/normalize_numeric_str.json, hand-derived, and asserted
///   against the Python-visible export by tests/test_vectors.py.
#[test]
fn normalize_numeric_str_matches_vectors() {
    for case in load(NORMALIZE_VECTORS, "normalize_numeric_str.json") {
        let input = case["input"].as_str().expect("input must be a string");
        let want = case["expected"].as_str();
        let got = numparse::normalize_numeric_str(input);
        assert_eq!(got.as_deref(), want, "normalize_numeric_str({input:?})");
    }
}

/// Verify `numparse::parse` against the shared vectors.
///
/// Mutation: admitting `e`, `+`, or `,` into the character filter, dropping
///   the parentheses-as-negation branch, or routing a decimal string to the
///   int path.
/// Oracle: vectors/parse.json, hand-derived from the documented semantics.
///   Note this is the same compiled code the Python suite reaches through
///   `libb.stats.parse`, so the two sides share an oracle rather than
///   cross-checking two implementations.
#[test]
fn parse_matches_vectors() {
    for case in load(PARSE_VECTORS, "parse.json") {
        let input = case["input"].as_str().expect("input must be a string");
        let want = expected_number(&case["expected"]);
        let got = numparse::parse(input);
        assert!(
            numbers_match(&got, &want),
            "parse({input:?}): got {got:?}, want {want:?}"
        );
    }
}

/// Verify `numparse::numify_str` against the shared vectors.
///
/// Mutation: stripping the percent suffix before detecting the accounting
///   parentheses, dropping the i64 range check so a large finite float is
///   cast anyway, or dropping the NaN/infinity guard on the int fallback.
/// Oracle: vectors/numify.json, the one table backed by two independent
///   implementations. Rows carrying a `divergence` marker assert the value
///   this kernel returns today rather than the Python one, so the known R4
///   disagreement is pinned instead of hidden.
#[test]
fn numify_str_matches_vectors() {
    for case in load(NUMIFY_VECTORS, "numify.json") {
        let input = case["input"].as_str().expect("input must be a string");
        let to = match case["to"].as_str().expect("to must be a string") {
            "int" => TargetType::Int,
            "float" => TargetType::Float,
            other => panic!("unknown target type {other:?}"),
        };
        let want = if case.get("divergence").is_some() {
            expected_number(&case["rust"])
        } else {
            expected_number(&case["expected"])
        };
        let got = numparse::numify_str(input, to);
        assert!(
            numbers_match(&got, &want),
            "numify_str({input:?}, {to:?}): got {got:?}, want {want:?}"
        );
    }
}

/// Verify `text::sanitize_vulgar_string` against the shared vectors.
///
/// Mutation: replacing matches left to right instead of in reverse (which
///   shifts every later offset), dropping the offset-0 leading-space
///   exception, or mistyping any one of the 15 fraction table values.
/// Oracle: vectors/sanitize_vulgar_string.json, which carries one row per
///   table entry. Note this is the same compiled code the Python suite
///   reaches through `libb.text`, so the two sides share an oracle rather
///   than cross-checking two implementations.
#[test]
fn sanitize_vulgar_string_matches_vectors() {
    for case in load(SANITIZE_VECTORS, "sanitize_vulgar_string.json") {
        let input = case["input"].as_str().expect("input must be a string");
        let want = case["expected"]
            .as_str()
            .expect("expected must be a string");
        assert_eq!(
            text::sanitize_vulgar_string(input),
            want,
            "sanitize_vulgar_string({input:?})"
        );
    }
}
