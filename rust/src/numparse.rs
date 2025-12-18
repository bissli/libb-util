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

/// Convert value to numeric type, handling common formatting.
///
/// Handles:
/// - Whitespace trimming
/// - Comma thousand separators
/// - Parentheses for negative numbers (accounting format)
/// - Percentage suffix (strips it, doesn't divide by 100)
pub fn numify_str(val: &str, to: TargetType) -> ParsedNumber {
    let val = val.trim();

    if val.is_empty() {
        return ParsedNumber::None;
    }

    // Check for parentheses notation (negative numbers in accounting format)
    let (val, is_negative) = if val.starts_with('(') && val.ends_with(')') {
        let inner = val[1..val.len() - 1].trim();
        if inner.is_empty() {
            return ParsedNumber::None;
        }
        (inner, true)
    } else {
        (val, false)
    };

    // Remove thousand separators (commas)
    let val: String = val.chars().filter(|&c| c != ',').collect();

    // Handle percentage notation (strip % suffix)
    let val = if val.ends_with('%') {
        val[..val.len() - 1].trim()
    } else {
        val.as_str()
    };

    if val.is_empty() {
        return ParsedNumber::None;
    }

    // Build the final string with sign
    let val = if is_negative {
        format!("-{}", val)
    } else {
        val.to_string()
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
