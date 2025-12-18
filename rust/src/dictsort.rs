//! Dictionary sorting utilities for libb.
//!
//! Implements `multikeysort` function equivalent to the Python version.
//! Uses pre-extracted values for O(n) value extraction instead of O(n log n).

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::cmp::Ordering;

/// Column sort specification.
struct SortColumn {
    key: String,
    descending: bool,
}

/// Pre-extracted sort key for a single item.
/// Stores values for all sort columns.
struct SortKey {
    index: usize,
    values: Vec<SortValue>,
}

/// A sortable value that handles None specially.
enum SortValue {
    None,
    Int(i64),
    Float(f64),
    Str(String),
    Other(PyObject), // Fallback for complex types
}

impl Clone for SortValue {
    fn clone(&self) -> Self {
        match self {
            SortValue::None => SortValue::None,
            SortValue::Int(v) => SortValue::Int(*v),
            SortValue::Float(v) => SortValue::Float(*v),
            SortValue::Str(v) => SortValue::Str(v.clone()),
            SortValue::Other(v) => Python::with_gil(|py| SortValue::Other(v.clone_ref(py))),
        }
    }
}

impl SortValue {
    fn from_pyany(obj: &Bound<'_, PyAny>) -> Self {
        if obj.is_none() {
            return SortValue::None;
        }
        // Try extracting as common types for efficient comparison
        if let Ok(v) = obj.extract::<i64>() {
            return SortValue::Int(v);
        }
        if let Ok(v) = obj.extract::<f64>() {
            return SortValue::Float(v);
        }
        if let Ok(v) = obj.extract::<String>() {
            return SortValue::Str(v);
        }
        // Fallback: store as PyObject
        SortValue::Other(obj.clone().unbind())
    }

    fn cmp_with(&self, other: &SortValue, py: Python<'_>) -> Ordering {
        match (self, other) {
            // None handling: None < anything
            (SortValue::None, SortValue::None) => Ordering::Equal,
            (SortValue::None, _) => Ordering::Less,
            (_, SortValue::None) => Ordering::Greater,

            // Same type comparisons (fast path)
            (SortValue::Int(a), SortValue::Int(b)) => a.cmp(b),
            (SortValue::Float(a), SortValue::Float(b)) => {
                a.partial_cmp(b).unwrap_or(Ordering::Equal)
            }
            (SortValue::Str(a), SortValue::Str(b)) => a.cmp(b),

            // Mixed numeric types
            (SortValue::Int(a), SortValue::Float(b)) => {
                (*a as f64).partial_cmp(b).unwrap_or(Ordering::Equal)
            }
            (SortValue::Float(a), SortValue::Int(b)) => {
                a.partial_cmp(&(*b as f64)).unwrap_or(Ordering::Equal)
            }

            // Fallback to Python comparison for Other or mixed types
            (SortValue::Other(a), SortValue::Other(b)) => py_cmp_objects(a, b, py),
            (SortValue::Other(a), _) => {
                let b_obj = other.to_pyobject(py);
                py_cmp_objects(a, &b_obj, py)
            }
            (_, SortValue::Other(b)) => {
                let a_obj = self.to_pyobject(py);
                py_cmp_objects(&a_obj, b, py)
            }

            // String vs non-string: use Python comparison
            _ => {
                let a_obj = self.to_pyobject(py);
                let b_obj = other.to_pyobject(py);
                py_cmp_objects(&a_obj, &b_obj, py)
            }
        }
    }

    fn to_pyobject(&self, py: Python<'_>) -> PyObject {
        match self {
            SortValue::None => py.None(),
            SortValue::Int(v) => v.into_py(py),
            SortValue::Float(v) => v.into_py(py),
            SortValue::Str(v) => v.into_py(py),
            SortValue::Other(v) => v.clone_ref(py),
        }
    }
}

/// Compare two Python objects.
fn py_cmp_objects(a: &PyObject, b: &PyObject, py: Python<'_>) -> Ordering {
    let a_bound = a.bind(py);
    let b_bound = b.bind(py);

    match a_bound.lt(b_bound) {
        Ok(true) => Ordering::Less,
        Ok(false) => match a_bound.gt(b_bound) {
            Ok(true) => Ordering::Greater,
            Ok(false) => Ordering::Equal,
            Err(_) => Ordering::Equal,
        },
        Err(_) => Ordering::Equal,
    }
}

/// Parse column specifications from Python list.
/// Columns prefixed with '-' are descending.
fn parse_columns(columns: &Bound<'_, PyAny>) -> PyResult<Vec<SortColumn>> {
    let mut result = Vec::new();

    // Handle single value or sequence
    if let Ok(s) = columns.extract::<String>() {
        // Single string column
        if let Some(key) = s.strip_prefix('-') {
            result.push(SortColumn {
                key: key.to_string(),
                descending: true,
            });
        } else {
            result.push(SortColumn {
                key: s,
                descending: false,
            });
        }
    } else if let Ok(list) = columns.downcast::<PyList>() {
        // List of columns
        for item in list.iter() {
            if let Ok(s) = item.extract::<String>() {
                if let Some(key) = s.strip_prefix('-') {
                    result.push(SortColumn {
                        key: key.to_string(),
                        descending: true,
                    });
                } else {
                    result.push(SortColumn {
                        key: s,
                        descending: false,
                    });
                }
            }
        }
    } else if let Ok(tuple) = columns.extract::<Vec<String>>() {
        // Tuple of columns
        for s in tuple {
            if let Some(key) = s.strip_prefix('-') {
                result.push(SortColumn {
                    key: key.to_string(),
                    descending: true,
                });
            } else {
                result.push(SortColumn {
                    key: s,
                    descending: false,
                });
            }
        }
    }

    Ok(result)
}

/// Get all known keys from a list of dicts.
fn get_known_keys(items: &Bound<'_, PyList>) -> PyResult<std::collections::HashSet<String>> {
    let mut keys = std::collections::HashSet::new();

    for item in items.iter() {
        if let Ok(dict) = item.downcast::<PyDict>() {
            for key in dict.keys() {
                if let Ok(s) = key.extract::<String>() {
                    keys.insert(s);
                }
            }
        }
    }

    Ok(keys)
}

/// Sort list of dictionaries by multiple keys.
///
/// Uses pre-extracted values for O(n) extraction instead of O(n log n).
///
/// Args:
///     items: List of dictionaries to sort.
///     columns: List of column names (prefix with '-' for descending).
///     inplace: If True, sort in place; otherwise return new sorted list.
///
/// Returns:
///     Sorted list if inplace=False, otherwise None.
#[pyfunction]
#[pyo3(signature = (items, columns, inplace=false))]
pub fn multikeysort<'py>(
    py: Python<'py>,
    items: &Bound<'py, PyList>,
    columns: &Bound<'py, PyAny>,
    inplace: bool,
) -> PyResult<Option<Py<PyList>>> {
    // Handle None columns
    if columns.is_none() {
        if inplace {
            return Ok(None);
        } else {
            let items_vec: Vec<PyObject> = items.iter().map(|x| x.unbind()).collect();
            let result = PyList::new_bound(py, items_vec);
            return Ok(Some(result.unbind()));
        }
    }

    // Parse column specifications
    let sort_columns = parse_columns(columns)?;

    // Get known keys from all dicts
    let known_keys = get_known_keys(items)?;

    // Filter columns to only those that exist
    let valid_columns: Vec<SortColumn> = sort_columns
        .into_iter()
        .filter(|col| known_keys.contains(&col.key))
        .collect();

    // If no valid columns, return as-is
    if valid_columns.is_empty() {
        if inplace {
            return Ok(None);
        } else {
            let items_vec: Vec<PyObject> = items.iter().map(|x| x.unbind()).collect();
            let result = PyList::new_bound(py, items_vec);
            return Ok(Some(result.unbind()));
        }
    }

    let len = items.len();

    // Pre-extract all values - O(n) operation
    let mut sort_keys: Vec<SortKey> = Vec::with_capacity(len);
    for i in 0..len {
        let item = items.get_item(i)?;
        let mut values = Vec::with_capacity(valid_columns.len());

        for col in &valid_columns {
            let val = item
                .get_item(&col.key)
                .ok()
                .map(|v| SortValue::from_pyany(&v))
                .unwrap_or(SortValue::None);
            values.push(val);
        }

        sort_keys.push(SortKey { index: i, values });
    }

    // Sort using pre-extracted values - comparisons are now fast
    sort_keys.sort_by(|a, b| {
        for (i, col) in valid_columns.iter().enumerate() {
            let cmp_result = a.values[i].cmp_with(&b.values[i], py);

            let final_cmp = if col.descending {
                cmp_result.reverse()
            } else {
                cmp_result
            };

            if final_cmp != Ordering::Equal {
                return final_cmp;
            }
        }
        Ordering::Equal
    });

    // Extract sorted indices
    let sorted_indices: Vec<usize> = sort_keys.iter().map(|k| k.index).collect();

    if inplace {
        // Reorder items in place
        let sorted_items: Vec<PyObject> = sorted_indices
            .iter()
            .map(|&i| items.get_item(i).unwrap().unbind())
            .collect();

        for (i, item) in sorted_items.into_iter().enumerate() {
            items.set_item(i, item)?;
        }
        Ok(None)
    } else {
        // Create new sorted list
        let sorted_items: Vec<PyObject> = sorted_indices
            .iter()
            .map(|&i| items.get_item(i).unwrap().unbind())
            .collect();
        let result = PyList::new_bound(py, sorted_items);
        Ok(Some(result.unbind()))
    }
}
