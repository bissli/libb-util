//! Iterator utilities for libb.
//!
//! Implements iterator transformation functions with optimized Rust implementations.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use std::collections::HashMap;

/// Recursively flatten nested lists/tuples into a single list.
///
/// Args:
///     args: Items to collapse (can be nested lists/tuples).
///
/// Returns:
///     Flattened list of items.
///
/// Examples:
///     >>> collapse([['a', ['b', ('c', 'd')]], -2, -1, [0, 1]])
///     ['a', 'b', 'c', 'd', -2, -1, 0, 1]
#[pyfunction]
#[pyo3(signature = (*args))]
pub fn collapse(py: Python<'_>, args: &Bound<'_, PyTuple>) -> PyResult<Py<PyList>> {
    let result = PyList::empty_bound(py);

    // Use explicit stack instead of recursion
    let mut stack: Vec<PyObject> = args.iter().rev().map(|item| item.unbind()).collect();

    while let Some(item) = stack.pop() {
        let bound_item = item.bind(py);

        // Check if item is a list or tuple (types to flatten)
        if let Ok(list) = bound_item.downcast::<PyList>() {
            // Push items in reverse order so they come out in correct order
            for i in (0..list.len()).rev() {
                if let Ok(elem) = list.get_item(i) {
                    stack.push(elem.unbind());
                }
            }
        } else if let Ok(tuple) = bound_item.downcast::<PyTuple>() {
            // Push items in reverse order
            for i in (0..tuple.len()).rev() {
                if let Ok(elem) = tuple.get_item(i) {
                    stack.push(elem.unbind());
                }
            }
        } else {
            // Not a list or tuple, add to result
            result.append(bound_item)?;
        }
    }

    Ok(result.unbind())
}

/// Back-fill a sorted array with the latest value.
///
/// Args:
///     values: List of values (may contain None).
///
/// Returns:
///     List with None values replaced by the most recent non-None value.
///
/// Examples:
///     >>> backfill([None, None, 1, 2, 3, None, 4])
///     [1, 1, 1, 2, 3, 3, 4]
#[pyfunction]
pub fn backfill(py: Python<'_>, values: &Bound<'_, PyList>) -> PyResult<Py<PyList>> {
    let len = values.len();
    if len == 0 {
        return Ok(PyList::empty_bound(py).unbind());
    }

    // First pass: find the first non-None value
    let mut first_value: Option<PyObject> = None;
    for i in 0..len {
        let item = values.get_item(i)?;
        if !item.is_none() {
            first_value = Some(item.unbind());
            break;
        }
    }

    // If all None, return copy of input
    let first_value = match first_value {
        Some(v) => v,
        None => return Ok(values.clone().unbind()),
    };

    let result = PyList::empty_bound(py);
    let mut latest = first_value.clone_ref(py);
    let mut pending_nones = 0usize;

    for i in 0..len {
        let item = values.get_item(i)?;

        if item.is_none() {
            if pending_nones > 0 || latest.bind(py).is_none() {
                // Still at the start, count pending
                pending_nones += 1;
            } else {
                // After we've seen a value, use latest
                result.append(&latest)?;
            }
        } else {
            // Got a non-None value
            latest = item.unbind();

            // Fill in any pending Nones at the start
            for _ in 0..pending_nones {
                result.append(&latest)?;
            }
            pending_nones = 0;

            result.append(&latest)?;
        }
    }

    Ok(result.unbind())
}

/// Back-fill a sorted iterdict with the latest values.
///
/// Args:
///     iterdict: List of dicts with possibly None values.
///
/// Returns:
///     List of dicts with None values replaced by most recent non-None values per key.
///
/// Examples:
///     >>> backfill_iterdict([{'a': 1, 'b': None}, {'a': 4, 'b': 2}, {'a': None, 'b': None}])
///     [{'a': 1, 'b': 2}, {'a': 4, 'b': 2}, {'a': 4, 'b': 2}]
#[pyfunction]
pub fn backfill_iterdict(py: Python<'_>, iterdict: &Bound<'_, PyList>) -> PyResult<Py<PyList>> {
    let len = iterdict.len();
    if len == 0 {
        return Ok(PyList::empty_bound(py).unbind());
    }

    // Track latest values and missing counts per key
    let mut latest: HashMap<String, PyObject> = HashMap::new();
    let mut missing: HashMap<String, usize> = HashMap::new();

    // Build result list
    let result = PyList::empty_bound(py);

    for i in 0..len {
        let item = iterdict.get_item(i)?;
        let dict = item.downcast::<PyDict>()?;

        let new_dict = PyDict::new_bound(py);

        for (key, value) in dict.iter() {
            let key_str: String = key.extract()?;

            if !value.is_none() {
                // Update latest value
                latest.insert(key_str.clone(), value.clone().unbind());

                // Fill in any pending items at the start
                if let Some(count) = missing.remove(&key_str) {
                    for j in 0..count {
                        if let Ok(prev_item) = result.get_item(j) {
                            if let Ok(prev_dict) = prev_item.downcast::<PyDict>() {
                                prev_dict.set_item(&key_str, latest.get(&key_str).unwrap())?;
                            }
                        }
                    }
                }

                new_dict.set_item(&key_str, &value)?;
            } else if let Some(latest_val) = latest.get(&key_str) {
                // Use latest value
                new_dict.set_item(&key_str, latest_val)?;
            } else {
                // Still at start, track missing
                *missing.entry(key_str.clone()).or_insert(0) += 1;
            }
        }

        result.append(new_dict)?;
    }

    Ok(result.unbind())
}

/// Compare two lists and check if elements in ref appear in same order in comp.
///
/// Args:
///     ref_list: Reference list of elements.
///     comp: Comparison list to check order against.
///
/// Returns:
///     True if all ref elements appear in comp in the same relative order.
///
/// Examples:
///     >>> same_order(['x', 'y', 'z'], ['x', 'a', 'b', 'y', 'd', 'z'])
///     True
///     >>> same_order(['x', 'y', 'z'], ['x', 'z', 'y'])
///     False
#[pyfunction]
pub fn same_order(ref_list: &Bound<'_, PyList>, comp: &Bound<'_, PyList>) -> PyResult<bool> {
    let ref_len = ref_list.len();
    let comp_len = comp.len();

    if comp_len < ref_len {
        return Ok(false);
    }

    // Build index map for comp list - O(n)
    // Note: We need to handle unhashable types, so we use linear search as fallback
    let mut indices: Vec<Option<usize>> = Vec::with_capacity(ref_len);

    for i in 0..ref_len {
        let ref_item = ref_list.get_item(i)?;
        let mut found = false;

        for j in 0..comp_len {
            let comp_item = comp.get_item(j)?;
            if ref_item.eq(&comp_item)? {
                indices.push(Some(j));
                found = true;
                break;
            }
        }

        if !found {
            return Ok(false);
        }
    }

    // Check if indices are in sorted order
    let mut prev_idx = 0usize;
    for (i, opt_idx) in indices.iter().enumerate() {
        if let Some(idx) = opt_idx {
            if i > 0 && *idx < prev_idx {
                return Ok(false);
            }
            prev_idx = *idx;
        }
    }

    Ok(true)
}
