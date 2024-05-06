import contextlib
import gzip
import shutil
import tarfile
import tempfile
from collections.abc import Iterable
from pathlib import Path

import numpy as np

with contextlib.suppress(Exception):
    import pandas as pd
    import pyarrow as pa

__all__ = ['is_null', 'download_tzdata']


def is_null(x):
    """Simple null/none checker
    """
    if isinstance(x, Iterable):
        with contextlib.suppress(Exception):
            return np.all(x.isna())
        return bool(x)
    with contextlib.suppress(Exception):
        if isinstance(x, pd._libs.missing.NAType):
            return True
    with contextlib.suppress(TypeError):
        if isinstance(x, pa.lib.NullScalar):
            return True
    with contextlib.suppress(TypeError):
        if np.isnat(x):
            return True
    with contextlib.suppress(TypeError):
        if np.isnan(x):
            return True
    return x is None


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
