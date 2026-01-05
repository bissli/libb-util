from __future__ import annotations

import logging
import operator
import types
from collections.abc import Iterable
from decimal import Decimal
from fractions import Fraction
from functools import reduce, wraps
from math import ceil, floor, isnan, log10, sqrt

import regex as re

from libb._rust import parse as _parse_impl
from libb.dicts import cmp
from libb.func import suppresswarning

logger = logging.getLogger(__name__)

__all__ = [
    'npfunc',
    'avg',
    'pct_change',
    'diff',
    'thresh',
    'isnumeric',
    'digits',
    'numify',
    'parse',
    'nearest',
    'covarp',
    'covars',
    'varp',
    'vars',
    'stddevp',
    'stddevs',
    'beta',
    'correl',
    'rsq',
    'rtns',
    'logrtns',
    'weighted_average',
    'linear_regression',
    'distance_from_line',
    'linterp',
    'np_divide',
    'safe_add',
    'safe_diff',
    'safe_divide',
    'safe_mult',
    'safe_round',
    'safe_cmp',
    'safe_min',
    'safe_max',
    'convert_mixed_numeral_to_fraction',
    'convert_to_mixed_numeral',
    'round_to_nearest',
    'numpy_smooth',
    'choose',
]

#
# Numpy decorators
#


def npfunc(nargs=1):
    """Decorator to convert args to numpy format and results back to Python.

    :param int nargs: Number of arguments to convert to numpy arrays.
    :returns: Decorator function.
    """
    def wrapper(fn):
        @wraps(fn)
        def wrapped_fn(*args, **kwargs):
            arr, args = [_tonp(args[i]) for i in range(nargs)], [args[i] for i in range(nargs, len(args))]
            return _topy(fn(*arr + args, **kwargs))
        return wrapped_fn
    return wrapper


def _tonp(x):
    """Handle None to NaN conversion"""
    import numpy as np
    if isinstance(x, (list, tuple)):
        return np.array([np.nan if k is None else k for k in x])
    return x


def _nptonumber(x):
    import numpy as np
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def _topy(x):
    """Replace np.nan with Python None"""
    import numpy as np
    if isinstance(x, (np.ndarray, types.GeneratorType)):
        return [_nptonumber(k) if not isnan(k) else None for k in x]  # keep None
    if isnan(x):
        return None
    return _nptonumber(x)


@suppresswarning
@npfunc(1)
def avg(x: Iterable):
    """Compute average of array, ignoring None/NaN values.

    :param Iterable x: Array of values.
    :returns: Average or None if all values are NaN.

    Example::

        >>> avg((-1.5, 2,))
        0.25
        >>> avg((None, 2,))
        2.0
        >>> avg((None, None,)) is None
        True
    """
    import numpy as np
    return np.nanmean([_ for _ in x if not np.isnan(_)])


@npfunc(1)
def pct_change(x: Iterable):
    """Compute percent change between consecutive elements.

    :param Iterable x: Array of values.
    :returns: Array of percent changes (first element is None).

    Example::

        >>> a = [1, 1, 1.5, 1, 2, 1.11, -1]
        >>> [f"{_:.2f}" if _ else _ for _ in pct_change(a)]
        [None, 0.0, '0.50', '-0.33', '1.00', '-0.44', '-1.90']
    """
    import numpy as np
    onep = np.array([np.nan])
    pchg = np.diff(x) / np.abs(x[:-1])
    return np.concatenate((onep, pchg), axis=0)


@npfunc(1)
def diff(x: Iterable):
    """Compute one-period difference between consecutive elements.

    :param Iterable x: Array of values.
    :returns: Array of differences (first element is None).

    Example::

        >>> [_ for _ in diff((0, 1, 3, 2, 1, 5, 4))]
        [None, 1.0, 2.0, -1.0, -1.0, 4.0, -1.0]
    """
    import numpy as np
    onep = np.array([np.nan])
    return np.concatenate((onep, np.diff(x)), axis=0)


#
# Math functions
#


def thresh(x, thresh=0.0):
    """Round to nearest integer if within threshold distance.

    :param float x: Number to potentially round.
    :param float thresh: Distance threshold for rounding.
    :returns: Rounded integer or original value.

    Positive Numbers::

        >>> thresh(74.9888, 0.05)
        75
        >>> thresh(75.01, 0.05)
        75

    Negative Numbers::

        >>> thresh(-74.988, 0.05)
        -75
        >>> thresh(-75.01, 0.05)
        -75

    Return Original::

        >>> thresh(74.90, 0.05)
        74.9
        >>> thresh(75.06, 0.05)
        75.06
    """
    assert thresh >= 0.0
    f, c = floor(x), ceil(x)
    if c - thresh < x:
        return c
    if f + thresh > x:
        return f
    return x


def isnumeric(x):
    """Check if value is a numeric type.

    :param x: Value to check.
    :returns: True if numeric (int, float, or numpy numeric).
    :rtype: bool
    """
    import numpy as np
    return np.issubdtype(x, np.integer) or np.issubdtype(x, np.floating) or isinstance(x, (int, float))


def digits(n):
    """Count number of integer digits in a number.

    :param n: Number to count digits of.
    :returns: Number of integer digits.
    :rtype: int

    Example::

        >>> digits(6e6)
        7
        >>> digits(100.01)
        3
        >>> digits(-6e5)==digits(-600000)==6
        True
        >>> digits(-100.)==digits(100)==3
        True
    """
    if n == 0:
        return 1
    return int(log10(abs(n))) + 1


def numify(val, to=float):
    """Convert value to numeric type, handling common formatting.

    Handles None values, already numeric values, and string formatting
    including whitespace, commas, parentheses (negative), and percentages.

    :param val: Value to convert.
    :param type to: Target type (default: float).
    :returns: Converted value or None if conversion fails.

    Example::

        >>> numify('1,234.56')
        1234.56
        >>> numify('(100)', to=int)
        -100
        >>> numify('50%')
        50.0
        >>> numify(None)
        >>> numify('')
    """
    if val is None:
        return None

    if isinstance(val, (int, float)):
        try:
            return to(val)
        except (ValueError, OverflowError):
            return None

    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None

        is_negative = False
        if val.startswith('(') and val.endswith(')'):
            val = val[1:-1].strip()
            if not val:
                return None
            is_negative = True

        val = val.replace(',', '')

        if val.endswith('%'):
            val = val[:-1].strip()
            if not val:
                return None

        if is_negative:
            val = f'-{val}'

        try:
            return to(val)
        except (ValueError, OverflowError):
            return None

    try:
        return to(val)
    except (ValueError, TypeError, OverflowError):
        return None


def parse(s):
    """Extract number from string.

    :param s: String to parse.
    :returns: Parsed int or float, or None if parsing fails.

    Example::

        >>> parse('1,200m')
        1200
        >>> parse('100.0')
        100.0
        >>> parse('100')
        100
        >>> parse('0.002k')
        0.002
        >>> parse('-1')==parse('(1)')==-1
        True
        >>> parse('-100.0')==parse('(100.)')==-100.0
        True
        >>> parse('')
    """
    return _parse_impl(str(s))


def nearest(num, decimals):
    """Round number to the nearest tick value.

    Useful for eliminating float errors after arithmetic operations.

    :param float num: Number to round.
    :param float decimals: Tick size to round to.
    :returns: Rounded number.
    :rtype: float

    Example::

        >>> nearest(401.4601, 0.01)
        401.46
        >>> nearest(401.46001, 0.0000000001)
        401.46001
    """
    if not num:
        return num
    tick = Decimal(str(decimals))
    return float(Decimal(round(num / decimals, 0)) * tick)


@npfunc(2)
def covarp(x, y):
    """Compute population covariance between x and y.

    :param x: First array.
    :param y: Second array (same length as x).
    :returns: Population covariance.
    :rtype: float

    Example::

        >>> x = [3, 2, 4, 5, 6]
        >>> y = [9, 7, 12, 15, 17]
        >>> "{:.5}".format(covarp(x, y))
        '5.2'
    """
    import numpy as np
    assert len(x) == len(y)
    assert len(x) > 0
    return np.cov(x, y, ddof=0)[0, 1]


@npfunc(2)
def covars(x, y):
    """Compute sample covariance between x and y.

    :param x: First array.
    :param y: Second array (same length as x).
    :returns: Sample covariance.
    :rtype: float

    Example::

        >>> x = [3, 2, 4, 5, 6]
        >>> y = [9, 7, 12, 15, 17]
        >>> "{:.5}".format(covars(x, y))
        '6.5'
    """
    import numpy as np
    assert len(x) == len(y)
    assert len(x) > 0
    return np.cov(x, y, ddof=1)[0, 1]


covar = covarp  # default, like Excel


@npfunc(1)
def varp(x):
    """Compute population variance of x.

    :param x: Array of values.
    :returns: Population variance.
    :rtype: float

    Example::

        >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
        >>> "{:.5}".format(varp(x))
        '678.84'
    """
    import numpy as np
    assert len(x) > 0
    return np.var(x, ddof=0)


@npfunc(1)
def vars(x):
    """Compute sample variance of x.

    :param x: Array of values.
    :returns: Sample variance.
    :rtype: float

    Example::

        >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
        >>> "{:.5}".format(vars(x))
        '754.27'
    """
    import numpy as np
    assert len(x) > 0
    return np.var(x, ddof=1)


var = vars  # default, like Excel


@npfunc(1)
def stddevp(x):
    """Compute population standard deviation.

    :param x: Array of values.
    :returns: Population standard deviation.
    :rtype: float

    Example::

        >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
        >>> "{:.5}".format(stddevp(x))
        '26.055'
    """
    import numpy as np
    return np.nanstd(x, ddof=0)


@npfunc(1)
def stddevs(x):
    """Compute sample standard deviation.

    :param x: Array of values.
    :returns: Sample standard deviation.
    :rtype: float

    Example::

        >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
        >>> "{:.5}".format(stddevs(x))
        '27.464'
    """
    import numpy as np
    return np.nanstd(x, ddof=1)


stddev = stddevs  # default, like Excel


@npfunc(2)
def beta(x, index):
    """Compute beta of x with respect to index (typically over returns).

    :param x: Asset returns.
    :param index: Index returns.
    :returns: Beta coefficient.
    :rtype: float

    Example::

        >>> x = [0.10, 0.18, -0.15, 0.18]
        >>> y = [0.10, 0.17, -0.17, 0.17]
        >>> '{:.2}'.format(beta(x, y))
        '0.97'
    """
    return covarp(x, index) / varp(index)


@npfunc(2)
def correl(x, y):
    """Compute correlation between x and y.

    :param x: First array.
    :param y: Second array.
    :returns: Correlation coefficient.
    :rtype: float

    Example::

        >>> x = [3, 2, 4, 5, 6]
        >>> y = [9, 7, 12, 15, 17]
        >>> "{:.3}".format(correl(x, y))
        '0.997'
    """
    import numpy as np
    assert len(x) == len(y)
    return np.corrcoef(x, y)[0, 1]


@npfunc(2)
def rsq(x, y):
    """Compute R-squared (coefficient of determination) between x and y.

    :param x: First array.
    :param y: Second array.
    :returns: R-squared value.
    :rtype: float

    Example::

        >>> x = [ 6, 5, 11, 7, 5, 4, 4]
        >>> y = [ 2, 3,  9, 1, 8, 7, 5]
        >>> "{:.5}".format(rsq(x, y))
        '0.05795'
    """
    import numpy as np
    assert len(x) == len(y)
    return np.corrcoef(x, y)[0, 1] ** 2


@npfunc(1)
def rtns(x):
    """Compute simple returns between consecutive values.

    :param x: Array of prices.
    :returns: Array of returns (one fewer element than input).

    Example::

        >>> pp = rtns([1., 1.1, 1.3, 1.1, 1.3])
        >>> [f'{x:0.2f}' for x in pp]
        ['0.10', '0.18', '-0.15', '0.18']
    """
    import numpy as np
    assert len(x) > 1
    return np.diff(x) / x[:-1]


@npfunc(1)
def logrtns(x):
    """Compute log returns between consecutive values.

    :param x: Array of prices.
    :returns: Array of log returns (one fewer element than input).

    Example::

        >>> pp = logrtns([1., 1.1, 1.3, 1.1, 1.3])
        >>> [f'{x:0.2f}' for x in pp]
        ['0.10', '0.17', '-0.17', '0.17']
    """
    import numpy as np
    assert len(x) > 1
    return np.diff(np.log(x))


def weighted_average(rows, field, predicate, weight_field):
    """Compute a weighted average of `field` in a DataSet using `weight_field`
    as the weight. Limit to rows matching the predicate. Uses sum of abs in
    denominator because we are really looking for the value-weighted contribution
    of the position.

    This handles long/short cases correctly, although they can give surprising results.

    Consider two "trades" BL 5000 at a delta of 50% and SS -4000 at a delta of 30%.
    If you didn't use abs() you'd get::

        (5000 * 50 - 4000 * 30) / (5000 - 4000) = 130

    Using abs() you get::

        (5000 * 50 - 4000 * 30) / (5000 + 4000) = 14.4

    This is really equivalent to saying you bought another 4000 at a delta of -30 (because
    the short position has a negative delta effect) which then makes more sense: combining
    two positions, one with positive delta and one with negative should give a value that weights
    the net effect of them, which the second case does. If the short position were larger or
    had a larger delta, you could end up with a negative weighted average, which although a bit
    confusing, is mathematically correct.
    """
    trows = [_ for _ in rows if predicate is None or predicate(_)]
    num = sum((_[field] or 0.0) * (_[weight_field] or 0.0) for _ in trows)
    den = sum(abs(_[weight_field] or 0.0) for _ in trows)
    return num / den if den else 0.0


@npfunc(2)
def linear_regression(x, y):
    """Compute the least-squares linear regression line for the set
    of points. Returns the slope and y-intercept.
    """
    import numpy as np
    A = np.vstack([x, np.ones(len(x))]).T
    m, b = np.linalg.lstsq(A, y)[0]
    return m, b


def distance_from_line(m, b, x, y):
    """Compute the distance from each point to the line defined by m and b."""
    import numpy as np
    x = np.array(x)
    y = np.array(y)
    return (-m * x + y - b) / sqrt(m * m + 1)


def linterp(x0, x1, x, y0, y1, *, inf_value=None):
    """Linearly interpolate y between y0 and y1 based on x's position.

    :param x0: Start of x range.
    :param x1: End of x range.
    :param x: Value to interpolate at.
    :param y0: Y value at x0.
    :param y1: Y value at x1.
    :param inf_value: Value to return when x1 is infinity (default: y0).
    :returns: Interpolated y value.
    :rtype: float

    Example::

        >>> linterp(1, 3, 2, 2, 4)
        3.0
        >>> linterp(1, float('inf'), 2, 2, 4)
        2.0
        >>> linterp(1, float('inf'), 2, 2, 4, inf_value=4)
        4.0
    """
    import numpy as np
    if x1 == float('inf'):
        return float(inf_value if inf_value is not None else y0)
    return float(np.interp(x, [x0, x1], [y0, y1]))


def np_divide(a, b):
    """Safely divide numpy arrays, returning 0 where divisor is 0.

    :param a: Numerator array.
    :param b: Denominator array.
    :returns: Result array with 0 where b was 0.
    """
    import numpy as np
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)


def safe_add(*args):
    """Safely add numbers, returning None if any argument is None.

    :param args: Numbers to add.
    :returns: Sum or None if any arg is None.
    """
    if not args:
        return None
    if None not in args:
        return reduce(operator.add, args)
    return None


def safe_diff(*args):
    """Safely subtract numbers, returning None if any argument is None.

    :param args: Numbers to subtract sequentially.
    :returns: Difference or None if any arg is None.
    """
    if not args:
        return None
    if None not in args:
        return reduce(operator.sub, args)
    return None


def safe_divide(*args, **kwargs):
    """Safely divide numbers, returning None if any arg is None.

    :param args: Numbers to divide sequentially.
    :param kwargs: Optional 'infinity' for division by zero result.
    :returns: Result or None if any arg is None, inf on division by zero.

    Example::

        >>> '{:.2f}'.format(safe_divide(10, 5))
        '2.00'
        >>> '{:.2f}'.format(safe_divide(10, 1.5, 1))
        '6.67'
        >>> safe_divide(1, 0)
        inf
        >>> safe_divide(10, 1, None)
    """
    if not args:
        return None
    if None not in args:
        if 0.0 in args[1:]:
            return kwargs.get('infinity', float('Inf'))
        return reduce(operator.truediv, args)
    return None


def safe_mult(*args):
    """For big lists of stuff to multiply, when some things may be None"""
    if not args:
        return None
    if None not in args:
        return reduce(operator.mul, args)
    return None


def safe_round(arg, places=2):
    """Safely round a number, returning None if argument is None.

    :param arg: Number to round.
    :param int places: Decimal places (default 2).
    :returns: Rounded number or None.
    """
    if arg is None:
        return None
    return round(float(arg), places)


def safe_cmp(op, a, b):
    """Compare two values using a comparison operator.

    :param op: Operator string ('>', '>=', '<', '<=', '==', '!=') or operator function.
    :param a: First value.
    :param b: Second value.
    :returns: Boolean result of comparison.
    """
    if op in {'>', operator.gt}:
        return cmp(a, b) == 1
    if op in {'>=', operator.ge}:
        return cmp(a, b) in {0, 1}
    if op in {'<', operator.lt}:
        return cmp(a, b) == -1
    if op in {'<=', operator.le}:
        return cmp(a, b) in {0, -1}
    if op in {'==', operator.eq}:
        return cmp(a, b) == 0
    if op in {'!=', '<>', operator.ne}:
        return cmp(a, b) != 0
    return op(a, b)


def _safe_min_max(agg, it=None, *args, **kwargs):
    """
    >>> min = safe_min
    >>> max = safe_max
    >>> min(2, 1), min([2, 1])
    (1, 1)
    >>> min(1, None), min(None, 1), min([1, None])
    (1, 1, 1)
    >>> min(1), min([1]), min(*[1])
    (1, 1, 1)
    >>> min(), min([]), min(*[])
    (None, None, None)
    >>> min(x for x in [])
    >>> min(None), min([None])
    (None, None)
    >>> max(1, 2), max([1, 2])
    (2, 2)
    """
    assert agg in {min, max}
    if isinstance(it, Iterable) and not args:
        it = [v for v in it if v is not None]
        if not it:
            return None
    if args:
        it = list(args) + [it]
        it = [v for v in it if v is not None]
        if not it:
            return None
    elif it:
        it = it if isinstance(it, Iterable) else [it]
    else:
        return None
    return agg(it, **kwargs)


def safe_min(*args, **kwargs):
    """Min returns None if it is in the list - this one returns the min value"""
    return _safe_min_max(min, *args, **kwargs)


def safe_max(*args, **kwargs):
    """Max returns None if it is in the list - this one returns the max value"""
    return _safe_min_max(max, *args, **kwargs)


_MIXED_NUMBER_FORMAT = re.compile(
    r"""^
    (?P<sign>[\-\+])?
    (?P<whole>\d+(?!\s*\/))?
    [\s-]*?
    (?:
        (?P<decimal>\.*\d*)
    |
        (?P<fraction>\d*\/\d*)
    )?
    $""",
    re.VERBOSE | re.IGNORECASE,
)


def convert_mixed_numeral_to_fraction(num: str):
    """Convert mixed numeral string to decimal fraction.

    :param str num: Mixed numeral (e.g., '1 7/8').
    :returns: Decimal equivalent.
    :rtype: float
    """
    return sum(float(Fraction(x)) for x in num.split(' '))


def convert_to_mixed_numeral(num, force_sign=False):
    """Convert decimal or fraction to mixed numeral string.

    :param num: Number or string to convert.
    :param bool force_sign: Force '+' prefix on positive numbers.
    :returns: Mixed numeral string (e.g., '1 7/8') or None on error.
    :rtype: str

    Example::

        >>> convert_to_mixed_numeral(1.875, True)
        '+1 7/8'
        >>> convert_to_mixed_numeral(-1.875)
        '-1 7/8'
        >>> convert_to_mixed_numeral(-.875)
        '-7/8'
        >>> convert_to_mixed_numeral('-1.875')
        '-1 7/8'
        >>> convert_to_mixed_numeral('1 7/8', False)
        '1 7/8'
        >>> convert_to_mixed_numeral('1-7/8', True)
        '+1 7/8'
        >>> convert_to_mixed_numeral('-1.5')
        '-1 1/2'
        >>> convert_to_mixed_numeral('6/7', True)
        '+6/7'
        >>> convert_to_mixed_numeral('1 6/7', False)
        '1 6/7'
        >>> convert_to_mixed_numeral(0)
        '0'
        >>> convert_to_mixed_numeral('0')
        '0'
    """
    try:
        num = float(num)
    except ValueError:
        pass
    except TypeError:
        return

    m = _MIXED_NUMBER_FORMAT.match(str(num))
    if m is None:
        logger.error(f'Invalid inputs for mixed number: {num!r}')
        return

    m = m.groupdict()

    sig = m.pop('sign') or ''
    num = safe_add(*[Fraction(str(v or 0)) for v in m.values()])
    num *= -1 if sig == '-' else 1
    num = num.limit_denominator(100)
    if not num:
        return '0'

    n, d = (num.numerator, num.denominator)
    m, p = divmod(abs(n), d)
    if n < 0:
        m = -m

    s = '+' if force_sign and (m > 0 or n > 0) else ''

    if m != 0 and p > 0:
        return f'{s}{m} {p}/{d}'
    if m != 0:
        return f'{s}{m}'
    return f'{s}{n}/{d}'


def round_to_nearest(value: float, base) -> float:
    """Round value to nearest multiple of base.

    :param float value: Value to round.
    :param base: Base multiple to round to (must be >= 1).
    :returns: Rounded value.
    :rtype: float

    Example::

        >>> round_to_nearest(12, 25)
        0
        >>> round_to_nearest(26, 25)
        25
    """
    assert base >= 1, 'This function is for base >= 1'
    if not value:
        return value
    return round(value / base) * base


def numpy_smooth(x, window_len=11, window='hanning'):
    """Smooth the data using a window with requested size.

    https://scipy-cookbook.readthedocs.io/items/SignalSmooth.html

    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.

    :param x: the input signal
    :param window_len: the dimension of the smoothing window; should be an odd integer
    :param window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'.
        Flat window will produce a moving average smoothing.
    :returns: the smoothed signal

    Example::

        t=linspace(-2,2,0.1)
        x=sin(t)+randn(len(t))*0.1
        y=smooth(x)

    .. seealso::
        numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve,
        scipy.signal.lfilter

    .. note::
        The window parameter could be the window itself if an array instead of a string.
        length(output) != length(input), to correct this: return
        y[(window_len/2-1):-(window_len/2)] instead of just y.
    """
    import numpy as np
    if x.ndim != 1:
        raise ValueError('Smooth only accepts 1 dimension arrays.')
    if x.size < window_len:
        raise ValueError('Input vector needs to be bigger than window size.')
    if window_len < 3:
        return x
    if window not in {'flat', 'hanning', 'hamming', 'bartlett', 'blackman'}:
        raise ValueError("Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'")
    s = np.r_[2 * x[0] - x[window_len - 1::-1], x, 2 * x[-1] - x[-1:-window_len:-1]]
    if window == 'flat':  # moving average
        w = np.ones(window_len, 'd')
    else:
        w = eval('np.' + window + '(window_len)')
    y = np.convolve(w / w.sum(), s, mode='same')
    return y[window_len:-window_len + 1]


def choose(n, k):
    """Compute binomial coefficient (n choose k).

    :param int n: Total items.
    :param int k: Items to choose.
    :returns: Number of combinations.
    :rtype: int

    Example::

        >>> choose(10, 3)
        120
    """
    return int(round(reduce(operator.mul, (float(n - i) / (i + 1) for i in range(k)), 1)))


if __name__ == '__main__':
    __import__('doctest').testmod()
