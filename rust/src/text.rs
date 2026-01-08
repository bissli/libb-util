//! Text processing utilities for libb.
//!
//! Implements text transformation functions with optimized Rust implementations.

use once_cell::sync::Lazy;
use pyo3::prelude::*;
use regex::Regex;
use std::collections::HashMap;

/// Vulgar fraction Unicode characters and their decimal values.
static VULGAR_FRACTIONS: Lazy<HashMap<char, f64>> = Lazy::new(|| {
    let mut m = HashMap::new();
    // Basic fractions: 1/4, 1/2, 3/4
    m.insert('\u{00BC}', 0.25);
    m.insert('\u{00BD}', 0.5);
    m.insert('\u{00BE}', 0.75);
    // Thirds
    m.insert('\u{2153}', 1.0 / 3.0);
    m.insert('\u{2154}', 2.0 / 3.0);
    // Fifths
    m.insert('\u{2155}', 0.2);
    m.insert('\u{2156}', 0.4);
    m.insert('\u{2157}', 0.6);
    m.insert('\u{2158}', 0.8);
    // Sixths
    m.insert('\u{2159}', 1.0 / 6.0);
    m.insert('\u{215A}', 5.0 / 6.0);
    // Eighths
    m.insert('\u{215B}', 0.125);
    m.insert('\u{215C}', 0.375);
    m.insert('\u{215D}', 0.625);
    m.insert('\u{215E}', 0.875);
    m
});

/// Pre-compiled regex for sanitize_vulgar_string.
/// Pattern matches: optional digits, optional whitespace, vulgar fraction character.
static VULGAR_REGEX: Lazy<Regex> = Lazy::new(|| {
    let fraction_chars: String = VULGAR_FRACTIONS.keys().collect();
    Regex::new(&format!(r"(\d*)\s*([{}])", regex::escape(&fraction_chars))).unwrap()
});

/// Replace vulgar fractions with decimal equivalents.
///
/// Converts number and vulgar fraction combinations to number and decimal.
///
/// Args:
///     s: String containing vulgar fractions.
///
/// Returns:
///     String with fractions converted to decimals.
///
/// Examples:
///     >>> sanitize_vulgar_string("Foo-Bar+Baz: 17s 4¾ 1 ⅛ 20 93¾ - 94⅛")
///     'Foo-Bar+Baz: 17s 4.75 1.125 20 93.75 - 94.125'
///     >>> sanitize_vulgar_string("⅓ cup")
///     '0.333333 cup'
#[pyfunction]
pub fn sanitize_vulgar_string(s: &str) -> String {
    let mut result = s.to_string();

    // Find all matches and collect them first (to avoid borrowing issues)
    let matches: Vec<_> = VULGAR_REGEX.captures_iter(s).collect();

    // Process matches in reverse order to preserve positions
    for caps in matches.into_iter().rev() {
        let full_match = caps.get(0).unwrap();
        let whole_num = caps.get(1).map(|m| m.as_str()).unwrap_or("");
        let frac_char = caps.get(2).map(|m| m.as_str()).unwrap_or("");

        if let Some(frac_val) = frac_char
            .chars()
            .next()
            .and_then(|c| VULGAR_FRACTIONS.get(&c))
        {
            let replacement = if whole_num.is_empty() {
                // Just the fraction - add leading space only if not at start of string
                let decimal = format_decimal(*frac_val);
                if full_match.start() == 0 {
                    decimal
                } else {
                    format!(" {}", decimal)
                }
            } else {
                // Number + fraction
                let whole: f64 = whole_num.parse().unwrap_or(0.0);
                format_decimal(whole + frac_val)
            };

            result.replace_range(full_match.start()..full_match.end(), &replacement);
        }
    }

    result
}

/// Format a decimal number, removing unnecessary trailing zeros.
fn format_decimal(val: f64) -> String {
    let rounded = (val * 1_000_000.0).round() / 1_000_000.0;
    let formatted = format!("{:.6}", rounded);
    let trimmed = formatted.trim_end_matches('0').trim_end_matches('.');
    trimmed.to_string()
}

/// Convert camelCase to snake_case.
///
/// Args:
///     camel: CamelCase string.
///
/// Returns:
///     snake_case string.
///
/// Examples:
///     >>> uncamel('CamelCase')
///     'camel_case'
///     >>> uncamel('CamelCamelCase')
///     'camel_camel_case'
///     >>> uncamel('getHTTPResponseCode')
///     'get_http_response_code'
#[pyfunction]
pub fn uncamel(camel: &str) -> String {
    let mut result = String::with_capacity(camel.len() + 10);
    let chars: Vec<char> = camel.chars().collect();

    for (i, &c) in chars.iter().enumerate() {
        if c.is_uppercase() {
            // Check if we need to insert underscore
            if i > 0 {
                let prev = chars[i - 1];
                let next = chars.get(i + 1).copied();

                // Insert underscore if:
                // 1. Previous char is lowercase or digit (e.g., "getH" -> "get_H", "get2H" -> "get2_H")
                // 2. Previous char is uppercase AND next char is lowercase (e.g., "HTTPResponse" -> "HTTP_Response")
                if prev.is_lowercase()
                    || prev.is_ascii_digit()
                    || (prev.is_uppercase() && next.is_some_and(|n| n.is_lowercase()))
                {
                    result.push('_');
                }
            }
            result.extend(c.to_lowercase());
        } else {
            result.push(c);
        }
    }

    result
}

/// Convert underscore_delimited_text to camelCase.
///
/// Args:
///     s: Underscore-delimited string.
///
/// Returns:
///     camelCase string.
///
/// Examples:
///     >>> underscore_to_camelcase('foo_bar_baz')
///     'fooBarBaz'
///     >>> underscore_to_camelcase('FOO_BAR')
///     'fooBar'
///     >>> underscore_to_camelcase('_foo_bar')
///     'fooBar'
#[pyfunction]
pub fn underscore_to_camelcase(s: &str) -> String {
    let mut result = String::with_capacity(s.len());
    let mut capitalize_next = false;

    for c in s.chars() {
        if c == '_' {
            capitalize_next = true;
        } else if capitalize_next && !result.is_empty() {
            result.extend(c.to_uppercase());
            capitalize_next = false;
        } else {
            result.extend(c.to_lowercase());
            capitalize_next = false;
        }
    }

    result
}
