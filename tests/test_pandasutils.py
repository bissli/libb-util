import contextlib

import numpy as np
import pandas as pd
import pytest

from libb import is_null
from libb.pandasutils import downcast, fuzzymerge


class TestIsNull:
    """Tests for is_null function."""

    def test_is_null_none(self):
        assert is_null(None) is True

    def test_is_null_zero(self):
        # 0 is not null
        assert is_null(0) is False

    def test_is_null_nan(self):
        assert is_null(np.nan) is True

    def test_is_null_date(self):
        import datetime
        assert is_null(datetime.date(2000, 1, 1)) is False

    def test_is_null_string(self):
        # Non-empty string is not null
        assert is_null('hello') is False

    def test_is_null_pyarrow_null(self):
        # Test NullScalar if pyarrow is available
        with contextlib.suppress(ImportError, RuntimeError):
            import pyarrow as pa

            # pa.NULL is the singleton NullScalar
            assert is_null(pa.NULL) is True


class TestDowncast:
    """Tests for downcast function."""

    def test_downcast_basic(self):
        data = {
            'integers': np.linspace(1, 100, 100),
            'floats': np.linspace(1, 1000, 100).round(2),
            'booleans': np.random.choice([1, 0], 100),
            'categories': np.random.choice(['foo', 'bar', 'baz'], 100),
        }
        df = pd.DataFrame(data)
        result = downcast(df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 100

    def test_downcast_with_tolerances(self):
        data = {'floats': np.linspace(1, 1000, 100).round(2)}
        df = pd.DataFrame(data)
        result = downcast(df, rtol=1e-10, atol=1e-10)
        assert isinstance(result, pd.DataFrame)

    def test_downcast_numpy_dtypes_only(self):
        data = {'integers': np.linspace(1, 100, 10)}
        df = pd.DataFrame(data)
        result = downcast(df, numpy_dtypes_only=True)
        assert isinstance(result, pd.DataFrame)


class TestFuzzymerge:
    """Tests for fuzzymerge function."""

    def test_fuzzymerge_basic(self):
        from rapidfuzz.fuzz import WRatio

        df1 = pd.DataFrame({
            'id': [1, 2, 3],
            'name': ['John Smith', 'Jane Doe', 'Bob Johnson'],
        })
        df2 = pd.DataFrame({
            'id': [10, 20, 30],
            'name': ['Jon Smith', 'Jane D', 'Bobby Johnson'],
        })
        result = fuzzymerge(df1, df2, right_on='name', left_on='name', scorer=WRatio)
        assert isinstance(result, pd.DataFrame)
        assert 'concat_value' in result.columns

    def test_fuzzymerge_without_concat_value(self):
        from rapidfuzz.fuzz import WRatio

        df1 = pd.DataFrame({
            'id': [1, 2],
            'name': ['Alice', 'Bob'],
        })
        df2 = pd.DataFrame({
            'id': [10, 20],
            'name': ['Alicia', 'Bobby'],
        })
        result = fuzzymerge(df1, df2, right_on='name', left_on='name', concat_value=False, scorer=WRatio)
        assert isinstance(result, pd.DataFrame)
        assert 'concat_value' not in result.columns

    def test_fuzzymerge_with_string_types(self):
        df1 = pd.DataFrame({'name': ['Test1', 'Test2']})
        df2 = pd.DataFrame({'name': ['Test 1', 'Test 2']})
        result = fuzzymerge(
            df1, df2,
            right_on='name', left_on='name',
            usedtype='uint8',
            scorer='partial_ratio',
        )
        assert isinstance(result, pd.DataFrame)


if __name__ == '__main__':
    pytest.main([__file__])
