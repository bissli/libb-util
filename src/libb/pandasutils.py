"""Pandas wrappers and utilities

This module provides utility functions for pandas DataFrames and Series,
including null checking, type downcasting, fuzzy merging, and timezone data.
"""
import contextlib
import gc
import gzip
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

with contextlib.suppress(Exception):
    from numexpr import evaluate

with contextlib.suppress(Exception):
    from numpy import amax, tile, where

with contextlib.suppress(Exception):
    from numpy import linspace, nan, random, uint8  # noqa

with contextlib.suppress(Exception):
    from pandas import DataFrame, isnull

with contextlib.suppress(Exception):
    from pandas import concat, read_csv  # noqa

with contextlib.suppress(Exception):
    from pdcast import downcast as pdc_downcast

with contextlib.suppress(Exception):
    import pdcast

with contextlib.suppress(Exception):
    from pyarrow.lib import NullScalar

with contextlib.suppress(Exception):
    from rapidfuzz.fuzz import partial_ratio  # noqa

with contextlib.suppress(Exception):
    from rapidfuzz.process import cdist

__all__ = ['is_null', 'download_tzdata', 'downcast', 'fuzzymerge']


def is_null(x):
    """Simple null/none checker (pandas required)

    >>> import datetime
    >>> import numpy as np
    >>> assert is_null(None)
    >>> assert not is_null(0)
    >>> assert is_null(np.nan)
    >>> assert not is_null(datetime.date(2000, 1, 1))

    """
    with contextlib.suppress(Exception):
        if isinstance(x, NullScalar):
            return True
    return isnull(x)


def download_tzdata():
    """Needed for pyarrow date wrangling. Goes into "Downloads" folder.
    """
    from libb import download_file, expandabspath

    base = Path(expandabspath('~/Downloads')) / 'tzdata'
    base.mkdir(exist_ok=True)
    temppath = Path(tempfile.gettempdir())

    tzgz = download_file(
        'https://data.iana.org/time-zones/releases/tzdata2022f.tar.gz',
        temppath / 'tzdata2022f.tar.gz',
    )
    with gzip.open(tzgz, 'rb') as fin:
        tztar = temppath / 'tzdata2022f.tar'
        with tztar.open('wb') as fout:
            shutil.copyfileobj(fin, fout)
            tarfile.open(tztar).extractall(base)

    zoneB = download_file(
        'https://raw.githubusercontent.com/unicode-org/cldr/master/common/supplemental/windowsZones.xml',
        temppath / 'windowsZones.xml',
    )
    with zoneB.open('rb') as fin, (base / 'windowsZones.xml').open('w') as fout:
        zonegz = gzip.GzipFile(fileobj=fin)
        fout.write(zonegz.read().decode())


def downcast(df: DataFrame, rtol=1e-05, atol=1e-08, numpy_dtypes_only=False):
    """Downcast pandas DataFrame to minimum viable type for each column,
    ensuring that resulting values are within tolerance of original values.

    RTOL: Default relative tolerance for numpy inexact numeric comparison
    See: https://numpy.org/doc/stable/reference/generated/numpy.allclose.html

    ATOL: Default absolute tolerance for numpy inexact numeric comparison
    See: https://numpy.org/doc/stable/reference/generated/numpy.allclose.html

    >>> data = {
    ... "integers": linspace(1, 100, 100),
    ... "floats": linspace(1, 1000, 100).round(2),
    ... "booleans": random.choice([1, 0], 100),
    ... "categories": random.choice(["foo", "bar", "baz"], 100)}
    >>> df = DataFrame(data)
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
    pdcast.options.RTOL = rtol
    pdcast.options.ATOL = atol
    return pdc_downcast(df, numpy_dtypes_only=numpy_dtypes_only)


def fuzzymerge(df1, df2, right_on, left_on, usedtype='uint8', scorer='WRatio',
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

    >>> df1 = read_csv(
    ...     "https://raw.githubusercontent.com/pandas-dev/pandas/main/doc/data/titanic.csv"
    ... )
    >>> df2 = df1.copy()
    >>> df2 = concat([df2 for x in range(3)], ignore_index=True)
    >>> df2.Name = (df2.Name + random.uniform(1, 2000, len(df2)).astype("U"))
    >>> df1 = concat([df1 for x in range(3)], ignore_index=True)
    >>> df1.Name = (df1.Name + random.uniform(1, 2000, len(df1)).astype("U"))
    >>> df3 = fuzzymerge(df1, df2, right_on='Name', left_on='Name', usedtype=uint8, scorer=partial_ratio,
    ...                         concat_value=True)
    >>> print(df3)
    """
    # Handle string type annotations
    if isinstance(usedtype, str):
        usedtype = eval(usedtype)
    if isinstance(scorer, str):
        scorer = eval(scorer)

    a = df1[right_on].__array__().astype('U')
    b = df2[left_on].__array__().astype('U')
    allcom = cdist(
        a,
        b,
        scorer=scorer,
        dtype=usedtype,
        workers=g if (g := os.cpu_count() - 1) > 1 else 1,
    )
    max_values = amax(allcom, axis=1)
    df1index, df2index = where(
        evaluate(
            'a==b',
            global_dict={},
            local_dict={'a': allcom,
                        'b': tile(max_values.reshape((-1, 1)), (1, allcom.shape[1]))},
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
