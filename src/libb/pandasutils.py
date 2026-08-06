"""Pandas wrappers and utilities

This module provides utility functions for pandas DataFrames and Series,
including null checking, type downcasting, fuzzy merging, and timezone data.
"""
import gc
import gzip
import os
import shutil
import tarfile
import tempfile
from pathlib import Path

__all__ = ['is_null', 'download_tzdata', 'downcast', 'fuzzymerge']


def is_null(x):
    """Check if value is null/None (pandas required).

    For array-like inputs (list, numpy array), returns True only if ALL
    elements are null. This avoids the "ambiguous truth value" error that
    occurs when using pandas.isnull() on arrays in boolean contexts.

    :param x: Value to check.
    :returns: True if value is null/None/NaN, or if array-like and all elements are null.
    :rtype: bool

    Example::

        >>> import datetime
        >>> import numpy as np
        >>> assert is_null(None)
        >>> assert not is_null(0)
        >>> assert is_null(np.nan)
        >>> assert not is_null(datetime.date(2000, 1, 1))
        >>> assert is_null([])
        >>> assert is_null([None, None])
        >>> assert not is_null([1, 2, 3])
        >>> assert not is_null([None, 1])
    """
    import numpy as np
    from pandas import isnull

    try:
        from pyarrow.lib import NullScalar
        if isinstance(x, NullScalar):
            return True
    except ImportError:
        pass

    if isinstance(x, np.ndarray):
        if x.size == 0:
            return True
        return all(is_null(v) for v in x.flat)
    if isinstance(x, list):
        if len(x) == 0:
            return True
        return all(is_null(v) for v in x)

    return isnull(x)


def download_tzdata():
    """Download timezone data for pyarrow date wrangling.

    Downloads to the "Downloads" folder.
    """
    from libb import download_file, expandabspath

    base = expandabspath('~/Downloads') / 'tzdata'
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
    shutil.copy(zoneB, base / 'windowsZones.xml')


def downcast(df, rtol=1e-05, atol=1e-08, numpy_dtypes_only=False):
    """Downcast DataFrame to minimum viable type for each column.

    Parameters
    ----------
    df : DataFrame
        DataFrame to downcast.
    rtol : float, default 1e-05
        Relative tolerance for numeric comparison.
    atol : float, default 1e-08
        Absolute tolerance for numeric comparison.
    numpy_dtypes_only : bool, default False
        Restrict the result to numpy dtypes, skipping pandas extension
        dtypes.

    Returns
    -------
    DataFrame
        Each column narrowed to the smallest type whose values stay
        within tolerance of the original.

    Notes
    -----
    - Tolerance follows the `numpy.allclose` convention: a candidate type
      is accepted when ``|a - b| <= atol + rtol * |b|`` for every value.
    - Tightening the tolerance widens the result, since fewer narrow types
      can represent the values: at rtol=atol=1e-10 the float column stays
      float64, and only at the looser default does it fit float32.

    Examples
    --------
    >>> from numpy import linspace, random
    >>> from pandas import DataFrame
    >>> data = {
    ... "integers": linspace(1, 100, 100),
    ... "floats": linspace(1, 1000, 100).round(2),
    ... "booleans": random.choice([1, 0], 100),
    ... "categories": random.choice(["foo", "bar", "baz"], 100)}
    >>> df = DataFrame(data)
    >>> tight = downcast(df, rtol=1e-10, atol=1e-10)
    >>> tight.dtypes['integers'], tight.dtypes['floats']
    (dtype('uint8'), dtype('float64'))
    >>> loose = downcast(df, rtol=1e-05, atol=1e-08)
    >>> loose.dtypes['integers'], loose.dtypes['floats']
    (dtype('uint8'), dtype('float32'))
    """
    import pdcast
    from pdcast import downcast as pdc_downcast
    pdcast.options.RTOL = rtol
    pdcast.options.ATOL = atol
    return pdc_downcast(df, numpy_dtypes_only=numpy_dtypes_only)


def fuzzymerge(df1, df2, right_on, left_on, usedtype='uint8', scorer='WRatio',
               concat_value=True, **kwargs):
    """Merge two DataFrames using fuzzy matching on specified columns.

    Performs fuzzy matching between DataFrames based on specified columns,
    useful for matching data with small variations like typos or abbreviations.

    :param DataFrame df1: First DataFrame to merge.
    :param DataFrame df2: Second DataFrame to merge.
    :param str right_on: Column name in df2 for matching.
    :param str left_on: Column name in df1 for matching.
    :param usedtype: Data type for distance matrix (default: uint8).
    :param scorer: Scoring function for fuzzy matching (default: WRatio).
    :param bool concat_value: Add similarity scores column (default: True).
    :param kwargs: Additional arguments for pandas.merge.
    :returns: Merged DataFrame with fuzzy-matched rows.
    :rtype: DataFrame

    Example::

        >>> df1 = read_csv(  # doctest: +SKIP
        ...     "https://raw.githubusercontent.com/pandas-dev/pandas/main/doc/data/titanic.csv"
        ... )
        >>> df2 = df1.copy()  # doctest: +SKIP
        >>> df2 = concat([df2 for x in range(3)], ignore_index=True)  # doctest: +SKIP
        >>> df2.Name = (df2.Name + random.uniform(1, 2000, len(df2)).astype("U"))  # doctest: +SKIP
        >>> df1 = concat([df1 for x in range(3)], ignore_index=True)  # doctest: +SKIP
        >>> df1.Name = (df1.Name + random.uniform(1, 2000, len(df1)).astype("U"))  # doctest: +SKIP
        >>> df3 = fuzzymerge(df1, df2, right_on='Name', left_on='Name', usedtype=uint8, scorer=partial_ratio,  # doctest: +SKIP
        ...                         concat_value=True)
    """
    from numexpr import evaluate
    from numpy import amax, tile, uint8  # noqa: F401 - uint8 used by eval
    from numpy import where
    from rapidfuzz.fuzz import partial_ratio  # noqa: F401 - used by eval
    from rapidfuzz.process import cdist

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
