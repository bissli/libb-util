"""Rust extension stubs.

This module re-exports Rust-accelerated functions from the native extension.
Stub implementations exist for Sphinx documentation generation.
"""

__all__ = ['multikeysort', 'parse']


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


try:
    from libb._libb import multikeysort, parse
except ImportError:
    pass
