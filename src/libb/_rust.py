"""Rust extension stubs.

This module re-exports Rust-accelerated functions from the native extension.
Stub implementations exist for Sphinx documentation generation.
"""

__all__ = [
    # Number parsing
    'parse',
    'normalize_numeric_str',
    # Dictionary sorting
    'multikeysort',
    # Text functions
    'sanitize_vulgar_string',
    'uncamel',
    'underscore_to_camelcase',
    # Iterator functions
    'collapse',
    'backfill',
    'backfill_iterdict',
    'same_order',
]


def multikeysort(items: list[dict], columns, inplace=False):
    """Sort list of dictionaries by multiple keys.

    :param list items: List of dictionaries to sort.
    :param columns: Column name(s) to sort by. Prefix with '-' for descending.
    :param bool inplace: If True, sort in place; otherwise return new list.
    :returns: Sorted list if inplace=False, otherwise None.
    """


def parse(s: str):
    """Extract number from string.

    :param str s: String to parse.
    :returns: Parsed int or float, or None if parsing fails.
    """


def normalize_numeric_str(s: str):
    """Strip accounting and thousands formatting from a numeric string.

    Applies the shared formatting rules without coercing to a type, so the
    caller keeps its own int/float policy. Commas are dropped, surrounding
    parentheses become a leading minus, and a trailing percent sign is
    removed rather than divided by 100.

    :param str s: String to normalize.
    :returns: Normalized string, or None when nothing is left to convert.
    :rtype: str | None
    """


def sanitize_vulgar_string(s: str) -> str:
    """Replace vulgar fractions with decimal equivalents.

    Converts number and vulgar fraction combinations to number and decimal.

    :param str s: String containing vulgar fractions.
    :returns: String with fractions converted to decimals.
    :rtype: str
    """


def uncamel(camel: str) -> str:
    """Convert camelCase to snake_case.

    :param str camel: CamelCase string.
    :returns: snake_case string.
    :rtype: str
    """


def underscore_to_camelcase(s: str) -> str:
    """Convert underscore_delimited_text to camelCase.

    :param str s: Underscore-delimited string.
    :returns: camelCase string.
    :rtype: str
    """


def collapse(*args, base_type=(tuple, list)):
    """Recursively flatten nested lists/tuples into a single list.

    :param args: Items to collapse.
    :param base_type: Types to recursively expand (default: tuple, list).
    :returns: Flattened list of items.
    :rtype: list
    """


def backfill(values: list) -> list:
    """Back-fill a sorted array with the latest value.

    :param list values: List of values (may contain None).
    :returns: List with None values replaced by the most recent non-None value.
    :rtype: list
    """


def backfill_iterdict(iterdict: list[dict]) -> list[dict]:
    """Back-fill a sorted iterdict with the latest values.

    :param list iterdict: List of dicts with possibly None values.
    :returns: List of dicts with None values replaced by most recent values per key.
    :rtype: list
    """


def same_order(ref: list, comp: list) -> bool:
    """Check if elements in ref appear in same order in comp.

    :param list ref: Reference list of elements.
    :param list comp: Comparison list to check order against.
    :returns: True if all ref elements appear in comp in the same relative order.
    :rtype: bool
    """


from libb._libb import backfill, backfill_iterdict, collapse, multikeysort
from libb._libb import normalize_numeric_str, parse, same_order
from libb._libb import sanitize_vulgar_string, uncamel, underscore_to_camelcase
