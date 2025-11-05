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


def fuzzymerge(df1, df2, right_on, left_on, usedtype=np.uint8, scorer=fuzz.WRatio,
               concat_value=True, **kwargs):
    """Merge two DataFrames using fuzzy matching on specified columns.

    This function performs a fuzzy matching between two DataFrames `df1` and `df2`
    based on the columns specified in `right_on` and `left_on`. Fuzzy matching allows
    you to find similar values between these columns, making it useful for matching
    data with small variations, such as typos or abbreviations.

    Parameters
    df1 (DataFrame): The first DataFrame to be merged.
    df2 (DataFrame): The second DataFrame to be merged.
    right_on (str): The column name in `df2` to be used for matching.
    left_on (str): The column name in `df1` to be used for matching.
    usedtype (numpy.dtype, optional): The data type to use for the distance matrix.
        Defaults to `np.uint8`.
    scorer (function, optional): The scoring function to use for fuzzy matching.
        Defaults to `fuzz.WRatio`.
    concat_value (bool, optional): Whether to add a 'concat_value' column in the result DataFrame,
        containing the similarity scores. Defaults to `True`.
    **kwargs: Additional keyword arguments to pass to the `pandas.merge` function.

    Returns
    DataFrame: A merged DataFrame with rows that matched based on the specified fuzzy criteria.

    >>> from rapidfuzz import fuzz
    >>> df1 = pd.read_csv(
    ...     "https://raw.githubusercontent.com/pandas-dev/pandas/main/doc/data/titanic.csv"
    ... )
    >>> df2 = df1.copy()
    >>> df2 = pd.concat([df2 for x in range(3)], ignore_index=True)
    >>> df2.Name = (df2.Name + np.random.uniform(1, 2000, len(df2)).astype("U"))
    >>> df1 = pd.concat([df1 for x in range(3)], ignore_index=True)
    >>> df1.Name = (df1.Name + np.random.uniform(1, 2000, len(df1)).astype("U"))
    >>> df3 = fuzzymerge(df1, df2, right_on='Name', left_on='Name', usedtype=np.uint8, scorer=fuzz.partial_ratio,
    ...                         concat_value=True)
    >>> print(df3)
    """
    a = df1[right_on].__array__().astype('U')
    b = df2[left_on].__array__().astype('U')
    allcom = process.cdist(
        a,
        b,
        scorer=scorer,
        dtype=usedtype,
        workers=g if (g := os.cpu_count() - 1) > 1 else 1,
    )
    max_values = np.amax(allcom, axis=1)
    df1index, df2index = np.where(
        ne.evaluate(
            'a==b',
            global_dict={},
            local_dict={'a': allcom,
                        'b': np.tile(max_values.reshape((-1, 1)), (1, allcom.shape[1]))},
        ))

    concatvalue = allcom[df1index, df2index].copy()
    del allcom
    gc.collect()
    kwargs['right_index'] = True
    kwargs['left_index'] = True
    toggi = df1.\
        iloc[df1index]\
        .reset_index(drop=False)\
        .merge(df2
               .iloc[df2index]
               .reset_index(drop=False),
               **kwargs)
    if concat_value:
        toggi['concat_value'] = concatvalue
    return toggi


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
