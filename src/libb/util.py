"""
DEPRECATED: This module has been broken up into specialized modules.

All functions from util.py have been moved to more appropriate locations:

- timeout → sync.py (synchronization primitive)
- same_order, coalesce, getitem → iter.py (sequence operations)
- backfill, backfill_iterdict, align_iterdict → iter.py (sequence processing)
- choose → stats.py (combinatorics)
- base64file, kryptophy → crypto.py (encoding/cryptography)
- suppresswarning → func.py (decorator)
- MultiMethod, multimethod → func.py (function utilities)
- is_numeric, fuzzy_search → text.py (text processing)
- scriptname → path.py (path operations)
- format_phone → format.py (formatting)
- merc_x, merc_y → geo.py (geographic projections)
- suppress_print, wrap_suppress_print → iolib.py (I/O operations)

Simply import from the top-level libb package:
    from libb import timeout, choose, fuzzy_search, etc.

This file is kept for backwards compatibility but contains no code.
"""

import warnings

warnings.warn(
    "libb.util is deprecated. Functions have been moved to specialized modules. "
    "Import from top-level libb instead: 'from libb import function_name'",
    DeprecationWarning,
    stacklevel=2
)

__all__ = []  # No exports
