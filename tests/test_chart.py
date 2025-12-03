import datetime

import numpy as np
import pytest

from libb.chart import NiceScale, numpy_timeseries_plot


class TestNiceScale:
    """Tests for NiceScale class."""

    def test_nice_scale_basic(self):
        ns = NiceScale(0, 100)
        assert ns.nice_min <= 0
        assert ns.nice_max >= 100
        assert ns.tick_spacing > 0

    def test_nice_scale_negative_range(self):
        ns = NiceScale(-50, 50)
        assert ns.nice_min <= -50
        assert ns.nice_max >= 50

    def test_nice_scale_small_range(self):
        ns = NiceScale(0.1, 0.5)
        assert ns.nice_min <= 0.1
        assert ns.nice_max >= 0.5
        assert ns.tick_spacing > 0

    def test_nice_scale_large_range(self):
        ns = NiceScale(0, 1000000)
        assert ns.nice_min <= 0
        assert ns.nice_max >= 1000000
        assert ns.tick_spacing > 0

    def test_nice_num_rounding(self):
        ns = NiceScale(0, 10)
        # Test that nice_num produces expected nice numbers
        assert ns.nice_num(1.2, True) == 1
        assert ns.nice_num(2.5, True) == 2
        assert ns.nice_num(4.0, True) == 5
        assert ns.nice_num(8.0, True) == 10

    def test_nice_num_no_rounding(self):
        ns = NiceScale(0, 10)
        assert ns.nice_num(1.0, False) == 1
        assert ns.nice_num(2.0, False) == 2
        assert ns.nice_num(4.0, False) == 5
        assert ns.nice_num(6.0, False) == 10

    def test_nice_scale_zero_range(self):
        """Test NiceScale handles zero range (constant values)."""
        ns = NiceScale(5, 5)
        # Should not raise and should have valid spacing
        assert ns.tick_spacing > 0

    def test_nice_num_zero_or_negative(self):
        """Test nice_num handles zero or negative values."""
        ns = NiceScale(0, 10)
        assert ns.nice_num(0, True) == 1
        assert ns.nice_num(-1, False) == 1


class TestNumpyTimeseriesPlot:
    """Tests for numpy_timeseries_plot function."""

    @pytest.fixture
    def sample_dates(self):
        """Generate sample dates for testing."""
        base = datetime.date(2023, 1, 1)
        return [base + datetime.timedelta(days=i) for i in range(10)]

    @pytest.fixture
    def sample_formatter(self):
        """Simple formatter for y-axis."""
        return lambda x, pos: f'{x:.1f}'

    def test_single_series(self, sample_dates, sample_formatter):
        """Test plotting a single time series."""
        series = [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        labels = ['Series 1']
        formats = [sample_formatter]

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'  # PNG header

    def test_two_series(self, sample_dates, sample_formatter):
        """Test plotting two overlapping time series."""
        series = [
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        ]
        labels = ['Series 1', 'Series 2']
        formats = [sample_formatter, sample_formatter]

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    def test_three_series_stacked(self, sample_dates, sample_formatter):
        """Test plotting three or more series in stacked subplots."""
        series = [
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
            [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],
        ]
        labels = ['Series 1', 'Series 2', 'Series 3']
        formats = [sample_formatter] * 3

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    def test_series_with_nan_values(self, sample_dates, sample_formatter):
        """Test that NaN values are properly masked.

        This test verifies the fix for the dimension mismatch bug where
        dates weren't masked along with the time series values.
        """
        series = [[1, 2, np.nan, 4, np.nan, 6, 7, np.nan, 9, 10]]
        labels = ['Series with NaN']
        formats = [sample_formatter]

        # This should not raise a dimension mismatch error
        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    def test_series_with_inf_values(self, sample_dates, sample_formatter):
        """Test that infinite values are properly masked."""
        series = [[1, 2, np.inf, 4, -np.inf, 6, 7, 8, 9, 10]]
        labels = ['Series with inf']
        formats = [sample_formatter]

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    def test_multiple_series_with_nan(self, sample_dates, sample_formatter):
        """Test multiple series where each has different NaN positions."""
        series = [
            [1, np.nan, 3, 4, 5, 6, 7, 8, 9, 10],
            [np.nan, 2, 3, np.nan, 5, 6, np.nan, 8, 9, np.nan],
        ]
        labels = ['Series 1', 'Series 2']
        formats = [sample_formatter, sample_formatter]

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'

    def test_empty_series_lists(self, sample_dates):
        """Test with empty series, labels, and formats."""
        buf = numpy_timeseries_plot('Test', sample_dates, [], [], [])

        assert buf is not None

    def test_default_none_parameters(self):
        """Test that None parameters default to empty lists."""
        dates = [datetime.date(2023, 1, 1)]
        buf = numpy_timeseries_plot('Test', dates)

        assert buf is not None

    def test_mismatched_lengths_raises(self, sample_dates, sample_formatter):
        """Test that mismatched series/labels/formats raises AssertionError."""
        series = [[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]]
        labels = ['Series 1', 'Extra Label']  # Mismatch
        formats = [sample_formatter]

        with pytest.raises(AssertionError):
            numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

    def test_constant_series_in_stacked_plot(self, sample_dates, sample_formatter):
        """Test stacked plot with constant values (zero range).

        This tests the fix for NiceScale handling zero range.
        """
        series = [
            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            [5, 5, 5, 5, 5, 5, 5, 5, 5, 5],  # Constant series
            [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        ]
        labels = ['Varying', 'Constant', 'Decreasing']
        formats = [sample_formatter] * 3

        buf = numpy_timeseries_plot('Test', sample_dates, series, labels, formats)

        assert buf is not None
        assert buf.getvalue()[:8] == b'\x89PNG\r\n\x1a\n'


if __name__ == '__main__':
    pytest.main([__file__])
