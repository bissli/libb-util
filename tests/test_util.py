import importlib
import warnings

import pytest


class TestUtilDeprecation:
    """Tests for deprecated util module."""

    def test_util_import_warns(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always')
            import libb.util
            importlib.reload(libb.util)  # Ensure warning fires
            assert len(w) >= 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert 'deprecated' in str(w[-1].message).lower()


if __name__ == '__main__':
    pytest.main([__file__])
