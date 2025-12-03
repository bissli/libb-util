import pytest

from libb import merc_x, merc_y


class TestMercator:
    """Tests for mercator projection functions."""

    def test_merc_x_zero(self):
        # 0 degrees longitude should be 0
        result = merc_x(0)
        assert abs(result) < 0.01

    def test_merc_y_zero(self):
        # 0 degrees latitude should be 0
        result = merc_y(0)
        assert abs(result) < 0.01

    def test_merc_x_known_value(self):
        # Known value from docstring
        result = merc_x(40.7484)
        assert abs(result - 4536091.139) < 1

    def test_merc_y_known_value(self):
        # Known value from docstring
        result = merc_y(73.9857)
        assert abs(result - 12468646.871) < 1

    def test_merc_y_clamps_extreme_latitudes(self):
        # Should clamp to 89.5 max
        result_90 = merc_y(90)
        result_89_5 = merc_y(89.5)
        assert abs(result_90 - result_89_5) < 0.01


if __name__ == '__main__':
    pytest.main([__file__])
