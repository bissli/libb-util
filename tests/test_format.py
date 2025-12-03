import datetime

import pytest
from asserts import assert_equal, assert_raises

from libb import Percent, capitalize, capwords, commafy, fmt, format_phone
from libb import format_timeinterval, splitcap, titlecase


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
    import datetime

    from libb import format_timeinterval
    start = datetime.datetime(2000, 1, 1, 12, 0, 0)
    end = datetime.datetime(2000, 1, 1, 12, 0, 30)
    result = format_timeinterval(start, end)
    assert result == '30 sec'


def test_secondsdelta():
    from libb import format_secondsdelta
    assert format_secondsdelta(30) == '30 sec'
    assert format_secondsdelta(90) == '1.5 min'
    assert format_secondsdelta(3600) == '60 min'
    assert format_secondsdelta(7200) == '2 hrs'


def test_timedelta():
    from libb import format_timedelta
    assert format_timedelta(datetime.timedelta(seconds=30)) == '30 sec'
    assert format_timedelta(datetime.timedelta(seconds=90)) == '1.5 min'
    assert format_timedelta(datetime.timedelta(hours=2)) == '2 hrs'
    assert format_timedelta(datetime.timedelta(days=3)) == '3 days'
    assert format_timedelta(datetime.timedelta(days=14)) == '2 wks'
    assert format_timedelta(datetime.timedelta(days=60)) == '2 mos'
    assert format_timedelta(datetime.timedelta(days=730)) == '2 yrs'
    assert format_timedelta(datetime.timedelta(microseconds=5000)) == '5 msec'


def test_no_style_returns_value():
    # Line 57 - value returned when no style provided
    assert fmt(1234.56, '') == 1234.56
    assert fmt(1234.56, None) == 1234.56


def test_timeinterval_no_end():
    # Line 156 - format_timeinterval with no end uses datetime.now()
    start = datetime.datetime.now() - datetime.timedelta(seconds=30)
    result = format_timeinterval(start)
    assert 'sec' in result


def test_commafy_edge_cases():
    # Lines 214, 217-218
    assert commafy(None) is None
    assert commafy(-1234) == '-1,234'
    assert commafy(-1234567.89) == '-1,234,567.89'


def test_splitcap():
    # Lines 244-253
    assert splitcap('foo_bar') == 'Foo Bar'
    assert splitcap('fooBar') == 'Foo Bar'
    assert splitcap('foo bar') == 'Foo Bar'
    assert splitcap('foo_bar_baz', '_') == 'Foo Bar Baz'


def test_capwords():
    # Lines 267-273
    assert capwords('f.o.o') == 'F.O.O'
    assert capwords('bar') == 'Bar'
    assert capwords('foo bar') == 'Foo Bar'
    # Acronyms stay uppercase
    assert capwords('FOO BAR') == 'FOO BAR'


def test_capitalize():
    # Lines 286-304
    assert capitalize('goo') == 'Goo'
    assert capitalize('mv') == 'MV'
    assert capitalize('pct') == '%'
    assert capitalize('mtd') == 'MTD'
    assert capitalize('qtd') == 'QTD'
    assert capitalize('ytd') == 'YTD'
    assert capitalize('pnl') == 'P&L'
    assert capitalize('usd') == '$'
    assert capitalize('vwap') == 'VWAP'


def test_titlecase():
    # Line 309
    assert titlecase('the quick brown fox') == 'The Quick Brown Fox'


def test_percent_class():
    # Lines 317-319
    p = Percent(0.5)
    assert p == 0.5
    assert p.pct is True


def test_format_phone():
    # Lines 328-333
    assert format_phone('6877995559') == '687-799-5559'
    assert format_phone('16877995559') == '1-687-799-5559'
    assert format_phone('7995559') == '-799-5559'


def test_format_string_input():
    # Test that string numeric inputs work correctly (only pure digits)
    result = fmt('123', '1p')
    assert result == '123.0'

    # Non-digit strings (like '-123') are returned unchanged per design
    result = fmt('-123', '1p')
    assert result == '-123'

    # Numeric values work correctly
    result = fmt(-123, '1p')
    assert result == '(123.0)'


def test_format_zero_with_short_scale():
    # Zero should work with 's' format without raising math domain error
    result = fmt(0, '1s')
    assert result == '0.0'
    result = fmt(0, '1S')
    assert result == '0.0'


if __name__ == '__main__':
    pytest.main([__file__])
