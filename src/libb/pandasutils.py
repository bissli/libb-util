import contextlib

import numpy as np

with contextlib.suppress(Exception):
    import pandas as pd
    import pyarrow as pa

__all__ = ['is_null']


def is_null(x):
    """Simple null/none checker
    """
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
