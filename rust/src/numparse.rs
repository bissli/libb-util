//! Core number parsing logic for libb.
//!
//! Implements `numify` and `parse` functions equivalent to the Python versions.

/// Result of parsing a number - can be int, float, or none.
#[derive(Debug, Clone, PartialEq)]
pub enum ParsedNumber {
    Int(i64),
    Float(f64),
    None,
}

/// Target type for numify conversion.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TargetType {
    Int,
    Float,
}

/// Strip accounting and thousands formatting from a numeric string.
///
/// The single implementation of the formatting rules that `numify_str` and
/// `libb.stats.numify` both apply. Each caller then imposes its own
/// coercion policy on the result: this function decides what the digits
/// are, not what type they become.
///
/// Applied in order:
/// - Trim surrounding whitespace.
/// - Surrounding parentheses mean negative (accounting format); the inner
///   text is trimmed again.
/// - Commas are removed wherever they appear (thousands separators).
/// - A trailing `%` is removed, NOT divided by 100.
/// - The accounting sign is prepended last, so it survives the suffix
///   strip.
///
/// Returns
/// -------
/// `None` when nothing is left to convert (empty input, empty parentheses,
/// or a bare suffix), otherwise the normalised digit string. A non-`None`
/// result is not a promise that it parses as a number.
pub fn normalize_numeric_str(val: &str) -> Option<String> {
    let val = val.trim();

    if val.is_empty() {
        return None;
    }

    let (val, is_negative) = if val.starts_with('(') && val.ends_with(')') {
        let inner = val[1..val.len() - 1].trim();
        if inner.is_empty() {
            return None;
        }
        (inner, true)
    } else {
        (val, false)
    };

    let val: String = val.chars().filter(|&c| c != ',').collect();

    let val = if val.ends_with('%') {
        val[..val.len() - 1].trim()
    } else {
        val.as_str()
    };

    if val.is_empty() {
        return None;
    }

    if is_negative {
        Some(format!("-{}", val))
    } else {
        Some(val.to_string())
    }
}

/// Convert a formatted numeric string to an int or a float.
///
/// Normalises with [`normalize_numeric_str`], then coerces. The coercion
/// policy here is deliberately NOT the one `libb.stats.numify` applies:
/// this falls back to an `f64` parse and truncates, where Python's `int()`
/// rejects a fractional or exponent string outright. `libtc`'s DataSet
/// type inference depends on that rejection, so the two policies are
/// pinned apart by the shared vectors rather than unified.
pub fn numify_str(val: &str, to: TargetType) -> ParsedNumber {
    let Some(val) = normalize_numeric_str(val) else {
        return ParsedNumber::None;
    };

    // Try to convert to target type
    match to {
        TargetType::Int => {
            // Try parsing as int first
            if let Ok(n) = val.parse::<i64>() {
                return ParsedNumber::Int(n);
            }
            // Try parsing as float then truncating
            if let Ok(f) = val.parse::<f64>() {
                // Check for overflow: inf, NaN, or outside i64 range
                if f.is_infinite() || f.is_nan() || f > i64::MAX as f64 || f < i64::MIN as f64 {
                    return ParsedNumber::None;
                }
                return ParsedNumber::Int(f as i64);
            }
            ParsedNumber::None
        }
        TargetType::Float => {
            if let Ok(f) = val.parse::<f64>() {
                return ParsedNumber::Float(f);
            }
            ParsedNumber::None
        }
    }
}

/// Extract number from string.
///
/// Extracts characters matching `[\(-\d\.\)]+` pattern, then determines
/// whether to return int or float based on whether the result contains a decimal.
pub fn parse(s: &str) -> ParsedNumber {
    // Extract numeric characters: digits, minus, parens, decimal point
    let num: String = s
        .chars()
        .filter(|&c| c.is_ascii_digit() || c == '-' || c == '(' || c == ')' || c == '.')
        .collect();

    if num.is_empty() {
        return ParsedNumber::None;
    }

    // Check if it should be int: remove special chars and check if all digits
    let stripped: String = num
        .chars()
        .filter(|&c| c != '-' && c != '(' && c != ')')
        .collect();

    // If no decimal point and all digits, try int
    if !stripped.contains('.') && stripped.chars().all(|c| c.is_ascii_digit()) {
        return numify_str(&num, TargetType::Int);
    }

    // Otherwise try float
    numify_str(&num, TargetType::Float)
}
