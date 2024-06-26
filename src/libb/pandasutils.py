import contextlib
import gzip
import shutil
import tarfile
import tempfile
from pathlib import Path

with contextlib.suppress(Exception):
    import pandas as pd
    import pyarrow as pa

__all__ = ['is_null', 'download_tzdata']


def is_null(x):
    """Simple null/none checker (pandas required)

    >>> import datetime
    >>> import numpy as np
    >>> assert is_null(None)
    >>> assert not is_null(0)
    >>> assert is_null(np.NaN)
    >>> assert not is_null(datetime.date(2000, 1, 1))

    """
    with contextlib.suppress(Exception):
        if isinstance(x, pa.lib.NullScalar):
            return True
    return pd.isnull(x)


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


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
