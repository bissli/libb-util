import datetime
import logging
import math
import re

from titlecase import titlecase as _titlecase

logger = logging.getLogger(__name__)

__all__ = [
    'Percent',
    'capitalize',
    'capwords',
    'commafy',
    'fmt',
    'format',
    'format_phone',
    'format_secondsdelta',
    'format_timedelta',
    'format_timeinterval',
    'splitcap',
    'titlecase'
    ]


def format(value, style):
    """Format a numeric value with various formatting options.

    Supports commas, parens for negative values, and special cases for zeros.

    :param value: Numeric value to format.
    :param str style: Format specification string.
    :returns: Formatted string.
    :rtype: str

    Style format: ``n[cpzZkKmMbBsS%#]/[kmb]`` (e.g., ``'2c'``, ``'0cpz'``, ``'1%'``, ``'1s'``)

    - **n** - number of decimals
    - **c** - use commas
    - **p** - wrap negative numbers in parenthesis
    - **z** - use a ' ' for zero values
    - **Z** - use a '-' for zero values
    - **K/k** - convert to thousands and add 'K' suffix
    - **M/m** - convert to millions and add 'M' suffix
    - **B/b** - convert to billions and add 'B' suffix
    - **S/s** - convert to shorter of KMB formats
    - **%** - scale by 100 and add a percent sign at the end (unless z/Z)
    - **#** - scale by 10000 and add 'bps' at the end
    - **/x** - divide the number by 1e3 (k), 1e6 (m), 1e9 (b) first
      (does not append the units like KMB do)

    Example::

        >>> format(1234.56, '2c')
        '1,234.56'
        >>> format(-100, '0cp')
        '(100)'
        >>> format(0, '2z')
        ''
        >>> format(0.5, '1%')
        '50.0%'
        >>> format(1500000, '1M')
        '1.5M'
    """
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == '':
        return ''
    if isinstance(value, str) and not value.isdigit():
        return value
    if not style:
        return value
    val = float(value)

    # verify the style
    m = re.match(r'^\+?(\d)([cpzZkKmMbBsS%#]{0,4})(/[kKmMbB])?$', style)
    if not m:
        raise ValueError('Invalid style:' + style)
    sign = style[0] == '+'
    dps, fmt, div = m.groups()

    # for a /x divisor, scale the number before doing any other formatting
    if div:
        val /= {'k': 1.0e3, 'm': 1.0e6, 'b': 1.0e9}[div[-1].lower()]

    # check for incompatible specifications
    if 'z' in fmt and 'Z' in fmt:
        raise ValueError('Invalid format. Cannot contain z and Z: ' + fmt)
    if 'p' in fmt and sign:
        raise ValueError('Invalid format. Cannot contain p and +: ' + fmt)
    if 's' in fmt.lower() and any(_ in fmt.lower() for _ in ('k', 'm', 'b')):
        raise ValueError('Invalid format. Cannot contain S and K/M/B: ' + fmt)
    if '%' in fmt and '#' in fmt:
        raise ValueError('Invalid format. Cannot contain % and #: ' + fmt)
    if ('%' in fmt or '#' in fmt) and any(_ in fmt.lower() for _ in ('s', 'k', 'm', 'b')):
        raise ValueError('Invalid format. Cannot contain %/# and S/K/M/B: ' + fmt)

    # now format it
    try:
        # handle zero specially, if requested
        if val == 0:
            if 'z' in fmt:
                return ''
            if 'Z' in fmt:
                return '-'

        # scale if using %, #, S, K, M or B formats
        suffix = ''
        factor = {'%': 1e2, '#': 1e4, 'k': 1e-3, 'K': 1e-3, 'm': 1e-6, 'M': 1e-6, 'b': 1e-9, 'B': 1e-9}
        for k in factor:
            if k in fmt:
                suffix = ' bp' if k == '#' else k
                val *= factor[k]
                break

        # if using S format, choose most appropriate of K, M or B
        if ('S' in fmt or 's' in fmt) and val != 0:
            e = math.log10(abs(val))
            for s, n, f in (('B', 9, 1e-9), ('M', 6, 1e-6), ('K', 3, 1e-3)):
                if e >= n:
                    suffix = s if 'S' in fmt else s.lower()
                    val *= f
                    break

        # set prefix and parens depending on sign of value and format settings
        prefix = ''
        parens = False
        if val < 0:
            if 'p' in fmt:
                parens = True
            else:
                prefix = '-'
            val = abs(val)
        elif val > 0:
            if sign:
                prefix = '+'

        # format the number to the specified number of decimal places
        s = f'%.{dps}f'
        val = s % val

        # check if formatted value is effectively zero
        is_zero = re.match(r'^0(\.0*)?$', val)

        # fix up with commas
        if 'c' in fmt:
            val = commafy(val)
        # wrap in parens
        if parens and not is_zero:
            val = f'({val})'
        elif 'p' in fmt:
            # pad positive numbers so the last digit lines up better
            val = f'{val}'

        # avoid +/-0s
        if prefix in {'-', '+'} and is_zero:
            prefix = ''
        val = prefix + val + suffix

        return val
    except Exception as exc:
        logger.exception(exc)
        return value or ''


#: Alias for :func:`format`.
fmt = format


def format_timeinterval(start, end=None):
    """Format a time interval as human-readable string.

    :param datetime start: Start datetime.
    :param datetime end: End datetime (defaults to now).
    :returns: Human-readable time interval string.
    :rtype: str

    Example::

        >>> start = datetime.datetime(2020, 1, 1, 12, 0, 0)
        >>> end = datetime.datetime(2020, 1, 1, 14, 30, 0)
        >>> format_timeinterval(start, end)
        '2.5 hrs'
    """
    if not end:
        end = datetime.datetime.now()

    return format_timedelta(end - start)


def format_secondsdelta(seconds):
    """Format seconds as human-readable time delta.

    :param float seconds: Number of seconds.
    :returns: Human-readable time string.
    :rtype: str

    Example::

        >>> format_secondsdelta(3661)
        '1.0 hrs'
        >>> format_secondsdelta(90)
        '1.5 min'
    """
    return format_timedelta(datetime.timedelta(0, seconds, 0))


def format_timedelta(td):
    """Format a timedelta as human-readable string.

    :param timedelta td: Time delta to format.
    :returns: Human-readable string (e.g., '2 hrs', '30 min').
    :rtype: str

    Example::

        >>> format_timedelta(datetime.timedelta(days=2))
        '2 days'
        >>> format_timedelta(datetime.timedelta(hours=3))
        '3 hrs'
        >>> format_timedelta(datetime.timedelta(seconds=45))
        '45 sec'
    """
    def fmt_num(val, units):
        if val == int(val):
            return f'{int(val)} {units}'
        return f'{val:.1f} {units}'

    if td.days > 365:
        return fmt_num(td.days / 365.0, 'yrs')
    if td.days > 30:
        return fmt_num(td.days / 30.0, 'mos')
    if td.days > 7:
        return fmt_num(td.days / 7.0, 'wks')
    if td.days > 0:
        return fmt_num(td.days + td.seconds / (60.0 * 60.0 * 24.0), 'days')
    if td.seconds > 3600:
        return fmt_num(td.seconds / 3600.0, 'hrs')
    if td.seconds > 60:
        return fmt_num(td.seconds / 60.0, 'min')
    if td.seconds > 0:
        return fmt_num(td.seconds + td.microseconds / 1000000.0, 'sec')
    return fmt_num(td.microseconds / 1000.0, 'msec')


def commafy(n):
    """Add commas to a numeric value.

    :param n: Number or string to add commas to.
    :returns: String with comma separators.
    :rtype: str or None

    Example::

        >>> commafy(1)
        '1'
        >>> commafy(123)
        '123'
        >>> commafy(-123)
        '-123'
        >>> commafy(1234)
        '1,234'
        >>> commafy(1234567890)
        '1,234,567,890'
        >>> commafy(123.0)
        '123.0'
        >>> commafy(1234.5)
        '1,234.5'
        >>> commafy(1234.56789)
        '1,234.56789'
        >>> commafy(f'{-1234.5:.2f}')
        '-1,234.50'
        >>> commafy(None)
        >>>
    """
    if n is None:
        return None
    n = str(n).strip()
    if n.startswith('-'):
        prefix = '-'
        n = n[1:].strip()
    else:
        prefix = ''
    if '.' in n:
        dollars, cents = n.split('.')
    else:
        dollars, cents = n, None
    r = []
    for i, c in enumerate(str(dollars)[::-1]):
        if i and (not (i % 3)):
            r.insert(0, ',')
        r.insert(0, c)
    out = ''.join(r)
    if cents:
        out += '.' + cents
    return prefix + out


def splitcap(s, delim=None):
    """Split and capitalize string by delimiter (or camelcase).

    :param str s: String to split and capitalize.
    :param str delim: Delimiter to split on (auto-detected if None).
    :returns: Title-cased string with spaces.
    :rtype: str

    Example::

        >>> splitcap("foo_bar")
        'Foo Bar'
        >>> splitcap("fooBar")
        'Foo Bar'
    """
    if not delim:
        if '_' in s:
            delim = '_'
        elif ' ' in s:
            delim = ' '
    if delim:
        bits = s.split(delim)
    else:  # camelcase
        bits = re.sub(r'([a-z])([A-Z])', r'\1 \2', s).split(' ')
    return ' '.join([capitalize(s) for s in bits])


def capwords(s):
    """Capitalize words in a string, accommodating acronyms.

    :param str s: String to capitalize.
    :returns: Capitalized string.
    :rtype: str

    Example::

        >>> capwords("f.o.o")
        'F.O.O'
        >>> capwords("bar")
        'Bar'
        >>> capwords("foo bar")
        'Foo Bar'
    """

    def _callback(match):
        s = match.group(0)
        if s == s.upper():
            return s
        return s.capitalize()

    return re.sub(r"[\w'\-\_]+", _callback, s)


def capitalize(s):
    """Capitalize with special handling for known abbreviations.

    :param str s: String to capitalize.
    :returns: Capitalized string or known abbreviation.
    :rtype: str

    Example::

        >>> capitalize('goo')
        'Goo'
        >>> capitalize('mv')
        'MV'
        >>> capitalize('pct')
        '%'
    """
    KNOWN = {
        'mtd': 'MTD',
        'qtd': 'QTD',
        'ytd': 'YTD',
        'xtd': 'XTD',
        'itd': 'ITD',
        'mv': 'MV',
        'lmv': 'LMV',
        'smv': 'SMV',
        'gmv': 'GMV',
        'nmv': 'NMV',
        'cs': 'CS',
        'pnl': 'P&L',
        'usd': '$',
        'dollar': '$',
        'pct': '%',
        'vwap': 'VWAP',
    }
    return KNOWN.get(s.lower(), capwords(s))


def titlecase(s):
    """Convert string to title case using python-titlecase library.

    :param str s: String to convert.
    :returns: Title-cased string.
    :rtype: str

    Example::

        >>> titlecase('the quick brown fox')
        'The Quick Brown Fox'
    """
    return _titlecase(s)


class Percent(float):
    """Float subclass that marks values for percentage formatting in display tables.

    Example::

        >>> p = Percent(0.25)
        >>> float(p)
        0.25
        >>> p.pct
        True
    """

    def __new__(cls, val):
        p = float.__new__(cls, val)
        p.pct = True
        return p


def format_phone(phone):
    """Reformat phone numbers for display.

    :param phone: Phone number as string or integer.
    :returns: Formatted phone number with dashes.
    :rtype: str

    Example::

        >>> format_phone('6877995559')
        '687-799-5559'
    """
    pstr = str(phone)
    parr = [pstr[-10:-7], pstr[-7:-4], pstr[-4:]]
    if len(pstr) > 10:
        parr.insert(0, pstr[:-10])
    formatted_phone = '-'.join(parr)
    return formatted_phone


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
