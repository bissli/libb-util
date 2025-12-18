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

/// Python module definition.
#[pymodule]
pub fn _libb(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Number parsing
    m.add_function(wrap_pyfunction!(parse, m)?)?;

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
