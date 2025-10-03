"""Pandas wrappers and utilities

Imported like pandas and wraps all pandas contents:
    from libb import pd
    df = pd.DataFrame()
"""
import contextlib
import gc
import os

with contextlib.suppress(ImportError, ModuleNotFoundError):
    import numexpr as ne
    import numpy as np
    import pandas as pd
    import pdcast as pdc
    from pandas import *
    from rapidfuzz import fuzz, process


def downcast(df: pd.DataFrame, rtol=1e-05, atol=1e-08, numpy_dtypes_only=False):
    """Downcast pandas DataFrame to minimum viable type for each column,
    ensuring that resulting values are within tolerance of original values.

    RTOL: Default relative tolerance for numpy inexact numeric comparison
    See: https://numpy.org/doc/stable/reference/generated/numpy.allclose.html

    ATOL: Default absolute tolerance for numpy inexact numeric comparison
    See: https://numpy.org/doc/stable/reference/generated/numpy.allclose.html

    >>> import numpy as np
    >>> data = {
    ... "integers": np.linspace(1, 100, 100),
    ... "floats": np.linspace(1, 1000, 100).round(2),
    ... "booleans": np.random.choice([1, 0], 100),
    ... "categories": np.random.choice(["foo", "bar", "baz"], 100)}
    >>> df = pd.DataFrame(data)
    >>> downcast(df, rtol=1e-10, atol=1e-10).info()
    <class 'pandas.core.frame.DataFrame'>
    ...
    dtypes: bool(1), category(1), float64(1), uint8(1)
    memory usage: 1.3 KB
    >>> downcast(df, rtol=1e-05, atol=1e-08).info()
    <class 'pandas.core.frame.DataFrame'>
    ...
    dtypes: bool(1), category(1), float32(1), uint8(1)
    memory usage: 964.0 bytes
    """
    pdc.options.RTOL = rtol
    pdc.options.ATOL = atol
    return pdc.downcast(df, numpy_dtypes_only=numpy_dtypes_only)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
