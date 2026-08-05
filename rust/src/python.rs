//! PyO3 bindings for libb functions.

use pyo3::prelude::*;

use crate::dictsort;
use crate::iter;
use crate::numparse::{self, ParsedNumber};
use crate::text;

/// Convert ParsedNumber to Python object.
fn to_py_object(py: Python<'_>, result: ParsedNumber) -> PyObject {
    match result {
        ParsedNumber::Int(n) => n.into_py(py),
        ParsedNumber::Float(f) => f.into_py(py),
        ParsedNumber::None => py.None(),
    }
}

/// Extract number from string.
///
/// Args:
///     s: String to parse.
///
/// Returns:
///     Parsed int or float, or None if parsing fails.
///
/// Examples:
///     >>> parse('1,200m')
///     1200
///     >>> parse('100.0')
///     100.0
///     >>> parse('(1)')
///     -1
#[pyfunction]
fn parse(py: Python<'_>, s: &str) -> PyObject {
    to_py_object(py, numparse::parse(s))
}

/// Strip accounting and thousands formatting from a numeric string.
///
/// Applies the shared formatting rules without coercing to a type, so the
/// caller keeps its own int/float policy. Commas are dropped, surrounding
/// parentheses become a leading minus, and a trailing percent sign is
/// removed rather than divided by 100.
///
/// Args:
///     s: String to normalize.
///
/// Returns:
///     The normalized string, or None when nothing is left to convert.
///
/// Examples:
///     >>> normalize_numeric_str('1,234.56')
///     '1234.56'
///     >>> normalize_numeric_str('(50%)')
///     '-50'
///     >>> normalize_numeric_str('  (  )  ')
#[pyfunction]
fn normalize_numeric_str(s: &str) -> Option<String> {
    numparse::normalize_numeric_str(s)
}

/// Python module definition.
#[pymodule]
pub fn _libb(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Number parsing
    m.add_function(wrap_pyfunction!(parse, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_numeric_str, m)?)?;

    // Dictionary sorting
    m.add_function(wrap_pyfunction!(dictsort::multikeysort, m)?)?;

    // Text functions
    m.add_function(wrap_pyfunction!(text::sanitize_vulgar_string, m)?)?;
    m.add_function(wrap_pyfunction!(text::uncamel, m)?)?;
    m.add_function(wrap_pyfunction!(text::underscore_to_camelcase, m)?)?;

    // Iterator functions
    m.add_function(wrap_pyfunction!(iter::collapse, m)?)?;
    m.add_function(wrap_pyfunction!(iter::backfill, m)?)?;
    m.add_function(wrap_pyfunction!(iter::backfill_iterdict, m)?)?;
    m.add_function(wrap_pyfunction!(iter::same_order, m)?)?;

    Ok(())
}
