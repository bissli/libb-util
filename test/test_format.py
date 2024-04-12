import pytest
from asserts import assert_equal, assert_raises

from libb import fmt


def test_bad_values():
    assert_equal('', fmt(None, ''))
    assert_equal('', fmt('', ''))
    assert_equal('not a number', fmt('not a number', ''))


def test_bad_formats():
    with assert_raises(ValueError):
        fmt(1234.5678, '+1p')
    with assert_raises(ValueError):
        fmt(1234.5678, '2%#')
    with assert_raises(ValueError):
        fmt(1234.5678, '0csk')
    with assert_raises(ValueError):
        fmt(1234.5678, '1s#')
    with assert_raises(ValueError):
        fmt(1234.5678, '2zZc')
    with assert_raises(ValueError):
        fmt(1078.2278, '-2')


def test_decimals():
    assert_equal('1078', fmt(1078.2278, '0'))
    assert_equal('1078.2', fmt(1078.2278, '1'))
    assert_equal('1078.23', fmt(1078.2278, '2'))
    assert_equal('1078.228', fmt(1078.2278, '3'))
    assert_equal('1078.2278', fmt(1078.2278, '4'))
    assert_equal('1078.22780', fmt(1078.2278, '5'))


def test_commas():
    assert_equal('1,234,567.8', fmt(1234567.8, '1c'))
    assert_equal('123,457', fmt(123456.78, '0c'))
    assert_equal('12,345.678', fmt(12345.678, '3c'))
    assert_equal('123.46', fmt(123.45678, '2c'))


def test_parens():
    assert_equal('123', fmt(123.4, '0p'))
    assert_equal('0', fmt(0.0, '0p'))
    assert_equal('(123.4)', fmt(-123.4, '1p'))


def test_sign():
    assert_equal('+123', fmt(123.4, '+0'))
    assert_equal('0', fmt(0.0, '+0'))
    assert_equal('-123.4', fmt(-123.4, '+1'))
    assert_equal('+153,102', fmt(153101.70, '+0c'))
    assert_equal('-15,592.45', fmt(-15592.448, '+2c'))


def test_zeros():
    assert_equal('', fmt(0, '0z'))
    assert_equal('123', fmt(123.4, '0Z'))
    assert_equal('-', fmt(0, '0Z'))
    assert_equal('123', fmt(123.4, '0Z'))


def test_scales():
    assert_equal('1.2B', fmt(1234567890.12, '1B'))
    assert_equal('1.2b', fmt(1234567890.12, '1b'))
    assert_equal('1235M', fmt(1234567890.12, '0M'))
    assert_equal('1235m', fmt(1234567890.12, '0m'))
    assert_equal('1234567.89K', fmt(1234567890.12, '2K'))
    assert_equal('1234567.89k', fmt(1234567890.12, '2k'))


def test_short_scales():
    assert_equal('1.2B', fmt(1234567890.12, '1S'))
    assert_equal('1.2b', fmt(1234567890.12, '1s'))
    assert_equal('12.35M', fmt(12345678.9012, '2S'))
    assert_equal('12.35m', fmt(12345678.9012, '2s'))
    assert_equal('123K', fmt(123456.789012, '0S'))
    assert_equal('123k', fmt(123456.789012, '0s'))


def test_percent():
    assert_equal('37%', fmt(0.372, '0%'))
    assert_equal('37.2%', fmt(0.372, '1%'))
    assert_equal('37.2%', fmt(0.372, '1%z'))
    assert_equal('', fmt(0.0, '1%z'))


def test_basis_points():
    assert_equal('37 bp', fmt(0.00372, '0#'))
    assert_equal('37.2 bp', fmt(0.00372, '1#'))
    assert_equal('37.2 bp', fmt(0.00372, '1#z'))
    assert_equal('', fmt(0.0, '1#z'))


def test_no_sign_on_zeros():
    assert_equal('0.0', fmt(0, '1'))
    assert_equal('0.0', fmt(0.01, '1'))
    assert_equal('0.0', fmt(-0.01, '1'))
    assert_equal('0.0', fmt(0, '+1'))
    assert_equal('0.0', fmt(0.01, '+1'))
    assert_equal('0.0', fmt(-0.01, '+1'))
    assert_equal('0.0', fmt(0, '1p'))
    assert_equal('0.0', fmt(0.01, '1p'))
    assert_equal('0.0', fmt(-0.01, '1p'))


def test_divisors():
    assert_equal('1.2', fmt(1234567890.12, '1/b'))
    assert_equal('1.2', fmt(1234567890.12, '1/B'))
    assert_equal('1235', fmt(1234567890.12, '0/M'))
    assert_equal('1235', fmt(1234567890.12, '0/m'))
    assert_equal('1234567.89', fmt(1234567890.12, '2/K'))
    assert_equal('1234567.89', fmt(1234567890.12, '2/k'))
    assert_equal('1,234.57', fmt(1234567890.12, '2c/m'))


# test time


def test_timeinterval():
    pass


def test_secondsdelta():
    pass


def test_timedelta():
    pass


if __name__ == '__main__':
    pytest.main([__file__])
