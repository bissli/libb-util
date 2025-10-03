import contextlib
import logging
import operator
import types
from collections.abc import Iterable
from decimal import Decimal
from fractions import Fraction
from functools import reduce, wraps
from math import ceil, floor, isnan, log10, sqrt

with contextlib.suppress(ImportError, ModuleNotFoundError):
    import numpy as np
    np.set_printoptions(linewidth=np.inf)

import regex as re

from libb.dictutils import cmp
from libb.util import suppresswarning

logger = logging.getLogger(__name__)


#
# Numpy decorators
#


def npfunc(nargs=1):
    """Convert input args into numpy input format, then convert result back to
    standard Python
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
    if isinstance(x, list | tuple):
        return np.array([np.nan if k is None else k for k in x])
    return x


def _nptonumber(x):
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, np.integer):
        return int(x)
    return x


def _topy(x):
    """Replace np.nan with Python None"""
    if isinstance(x, np.ndarray | types.GeneratorType):
        return [_nptonumber(k) if not isnan(k) else None for k in x]  # keep None
    if isnan(x):
        return None
    return _nptonumber(x)


@suppresswarning
@npfunc(1)
def avg(x: Iterable):
    """Average of array x

    >>> avg((-1.5, 2,))
    0.25
    >>> avg((None, 2,))
    2.0
    >>> avg((None, None,)) is None
    True
    """
    return np.nanmean([_ for _ in x if not np.isnan(_)])


@npfunc(1)
def pct_change(x: Iterable):
    """Percent change of elements in array x

    Should allow args or array

    >>> a = [1, 1, 1.5, 1, 2, 1.11, -1]
    >>> [f"{_:.2f}" if _ else _ for _ in pct_change(a)]
    [None, 0.0, '0.50', '-0.33', '1.00', '-0.44', '-1.90']
    """
    onep = np.array([np.nan])
    pchg = np.diff(x) / np.abs(x[:-1])
    return np.concatenate((onep, pchg), axis=0)


@npfunc(1)
def diff(x: Iterable):
    """One period diff function

    >>> [_ for _ in diff((0, 1, 3, 2, 1, 5, 4))]
    [None, 1.0, 2.0, -1.0, -1.0, 4.0, -1.0]
    """
    onep = np.array([np.nan])
    return np.concatenate((onep, np.diff(x)), axis=0)


#
# Math functions
#


# move out
def thresh(x, thresh=0.0):
    """Rounding function that rounds up or down by to nearest whole number
    if the number is within a threshold distance

    Positive numbers
    >>> thresh(74.9888, 0.05)
    75
    >>> thresh(75.01, 0.05)
    75

    Negative numbers
    >>> thresh(-74.988, 0.05)
    -75
    >>> thresh(-75.01, 0.05)
    -75

    Return original
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
    return np.issubdtype(x, np.integer) or np.issubdtype(x, np.floating) or isinstance(x, int | float)


# move out
def digits(n):
    """Number of digits

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


# move out
def numify(val, to=float):
    """Return float from string"""
    if val is None:
        return val
    if isinstance(val, int | float):
        return to(val)
    if isinstance(val, str):
        val = val.strip()
        if not val:
            return None
        val = val.replace(',', '')
        if val.startswith('(') and val.endswith(')'):
            val = val.replace('(', '').replace(')', '')
            return -1.0 * to(val)
    return to(val)


# move out
def parse(s):
    """Extract number from string

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
    try:
        num = ''.join(re.findall(r'[\(-\d\.\)]+', str(s)))
        if re.sub(r'[-\(\)]', '', num).isdigit():
            return numify(num, int)
        return numify(num, float)
    except:
        pass


# move out
def nearest(num, decimals):
    """Given a number, round it to the nearest tick. Very useful for sussing
    float error out of numbers. Use this after adding/subtracting/multiplying
    numbers.

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
    """Population covariance between x and y (n)

    >>> x = [3, 2, 4, 5, 6]
    >>> y = [9, 7, 12, 15, 17]
    >>> "{:.5}".format(covarp(x, y))
    '5.2'
    """
    assert len(x) == len(y)
    assert len(x) > 0
    return np.cov(x, y, ddof=0)[0, 1]


@npfunc(2)
def covars(x, y):
    """Sample covariance between x and y (n)

    >>> x = [3, 2, 4, 5, 6]
    >>> y = [9, 7, 12, 15, 17]
    >>> "{:.5}".format(covars(x, y))
    '6.5'
    """
    assert len(x) == len(y)
    assert len(x) > 0
    return np.cov(x, y, ddof=1)[0, 1]


covar = covarp  # default, like Excel


@npfunc(1)
def varp(x):
    """Population variance of x (n)

    >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
    >>> "{:.5}".format(varp(x))
    '678.84'
    """
    assert len(x) > 0
    return np.var(x, ddof=0)


@npfunc(1)
def vars(x):
    """Sample variance of x (n)

    >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
    >>> "{:.5}".format(vars(x))
    '754.27'
    """
    assert len(x) > 0
    return np.var(x, ddof=1)


var = vars  # default, like Excel


@npfunc(1)
def stddevp(x):
    """
    >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
    >>> "{:.5}".format(stddevp(x))
    '26.055'
    """
    return np.nanstd(x, ddof=0)


@npfunc(1)
def stddevs(x):
    """
    >>> x = [1345, 1301, 1368, 1322, 1310, 1370, 1318, 1350, 1303, 1299]
    >>> "{:.5}".format(stddevs(x))
    '27.464'
    """
    return np.nanstd(x, ddof=1)


stddev = stddevs  # default, like Excel


@npfunc(2)
def beta(x, index):
    """Beta of x with respect to index, generally over returns

    >>> x = [0.10, 0.18, -0.15, 0.18]
    >>> y = [0.10, 0.17, -0.17, 0.17]
    >>> '{:.2}'.format(beta(x, y))
    '0.97'
    """
    return covarp(x, index) / varp(index)


@npfunc(2)
def correl(x, y):
    """Correlation between x and y

    >>> x = [3, 2, 4, 5, 6]
    >>> y = [9, 7, 12, 15, 17]
    >>> "{:.3}".format(correl(x, y))
    '0.997'
    """
    assert len(x) == len(y)
    return np.corrcoef(x, y)[0, 1]


@npfunc(2)
def rsq(x, y):
    """Correlation coefficient between x and y

    >>> x = [ 6, 5, 11, 7, 5, 4, 4]
    >>> y = [ 2, 3,  9, 1, 8, 7, 5]
    >>> "{:.5}".format(rsq(x, y))
    '0.05795'
    """
    assert len(x) == len(y)
    return np.corrcoef(x, y)[0, 1] ** 2


@npfunc(1)
def rtns(x):
    """Returns between consecutive values in x

    >>> pp = rtns([1., 1.1, 1.3, 1.1, 1.3])
    >>> [f'{x:0.2f}' for x in pp]
    ['0.10', '0.18', '-0.15', '0.18']
    """
    assert len(x) > 1
    return np.diff(x) / x[:-1]


@npfunc(1)
def logrtns(x):
    """Natural logarithm of returns between consecurive values in x

    >>> pp = logrtns([1., 1.1, 1.3, 1.1, 1.3])
    >>> [f'{x:0.2f}' for x in pp]
    ['0.10', '0.17', '-0.17', '0.17']
    """
    assert len(x) > 1
    return np.diff(np.log(x))


def weighted_average(rows, field, predicate, weight_field):
    """Compute a weighted average of `field` in a DataSet using `weight_field`
    as the weight. Limit to rows matching the predicate. Uses sum of abs in
    denominator because we are really looking for the value-weighted contribution
    of the position.

    This handles long/short cases correctly, although they can give surprising results.

    Consider two "trades" BL 5000 at a delta of 50% and SS -4000 at a delta of 30%.
    If you didn't use abs() you'd get:
       (5000 * 50 - 4000 * 30) / (5000 - 4000) = 130
    Using abs() you get:
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
    A = np.vstack([x, np.ones(len(x))]).T
    m, b = np.linalg.lstsq(A, y)[0]
    return m, b


def distance_from_line(m, b, x, y):
    """Compute the distance from each point to the line defined by m and b."""
    x = np.array(x)
    y = np.array(y)
    return (-m * x + y - b) / sqrt(m * m + 1)


def linterp(x0, x1, x, y0, y1):
    """Linearly interpolate y between y0 and y1 based on x's distance between x0 and x1
    >>> linterp(1, 3, 2, 2, 4)
    3.0
    >>> linterp(1, float('inf'), 2, 2, 4)
    2.0
    """
    return float(np.interp(x, [x0, x1], [y0, y1]))


def np_divide(a, b):
    """Allow divide where b may have a 0"""
    return np.divide(a, b, out=np.zeros_like(a), where=b != 0)


def safe_add(*args):
    if not args:
        return None
    if None not in args:
        return reduce(operator.add, args)
    return None


def safe_diff(*args):
    if not args:
        return None
    if None not in args:
        return reduce(operator.sub, args)
    return None


def safe_divide(*args, **kwargs):
    """
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
    if arg is None:
        return None
    return round(float(arg), 2)


def safe_cmp(op, a, b):
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
        if not len(it):
            return None
    if args:
        it = list(args) + [it]
        it = [v for v in it if v is not None]
        if not len(it):
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
    """Basic reverse operation of `convert_to_mixed_numeral`"""
    return sum(float(Fraction(x)) for x in num.split(' '))


def convert_to_mixed_numeral(num, force_sign=False):
    """
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
    """Simple function to round to nearest base

    >>> round_to_nearest(12, 25)
    0
    >>> round_to_nearest(26, 25)
    25

    """
    assert base >= 1, 'This function is for base >= 1'
    if not value:
        return value
    return round(value / base) * base


class BBox:
    """Bounding box for use with `overlaps` and `push_apart` functions"""

    def __init__(self, x_coord, y_coord, width, height, name=''):
        self.x = float(x_coord)
        self.y = float(y_coord)
        self.w = float(width)
        self.h = float(height)
        self.name = name

    def __repr__(self):
        return f'BBox({self.name}({self.x:.3f},{self.y:.3f}), '\
               f'{self.x_min:.3f}:{self.x_max:.3f}, '\
               f'{self.y_min:.3f}:{self.y_max:.3f})'

    @property
    def a(self):
        return self.w * self.h

    @property
    def d(self):
        """Diagonal, longest part of the box"""
        return sqrt((self.rx**2) + (self.ry**2))

    @property
    def rx(self):
        return self.w / 2.0

    @property
    def ry(self):
        return self.h / 2.0

    @property
    def x_min(self):
        return self.x - self.rx

    @property
    def y_min(self):
        return self.y - self.ry

    @property
    def x_max(self):
        return self.x + self.rx

    @property
    def y_max(self):
        return self.y + self.ry


def overlaps(*boxes):
    x_min = min(boxes, key=lambda c: c.x)
    y_min = min(boxes, key=lambda c: c.y)
    x_max = max(boxes, key=lambda c: c.x)
    y_max = max(boxes, key=lambda c: c.y)
    return (x_min.x + x_min.rx) >= (x_max.x - x_max.rx) or (y_min.y + y_min.ry) >= (y_max.y - y_max.ry)


def push_apart(*boxes):
    """Push apart bounding boxes until they do not overlap

    From idea for https://stackoverflow.com/a/10739207

    >>> a = BBox(1, 1, 4, 2, 'a')
    >>> a
    BBox(a(1.000,1.000), -1.000:3.000, 0.000:2.000)
    >>> b = BBox(1, 2, 3, 3, 'b')
    >>> b
    BBox(b(1.000,2.000), -0.500:2.500, 0.500:3.500)

    >>> push_apart(a, b)
    >>> a
    BBox(a(4.045,-2.045), 2.045:6.045, -3.045:-1.045)
    >>> b
    BBox(b(0.067,5.225), -1.433:1.567, 3.725:6.725)
    """
    tries = 0
    max_tries = 100
    while overlaps(*boxes):
        centroid_x = avg([x.x for x in boxes])
        centroid_y = avg([x.y for x in boxes])
        for box in boxes:
            dist = sqrt(((centroid_x - box.x) ** 2) + ((centroid_y - box.y) ** 2))
            move = sqrt(((box.d - dist) ** 2) / 2.0)  # move by same x and y
            box.x += -1.0 * move if box.x < centroid_x else move
            box.y += -1.0 * move if box.y < centroid_y else move
        tries += 1
        if tries > max_tries:
            raise AssertionError('Exceeded 100 tries to push apart')


def numpy_smooth(x: 'np.ndarray', window_len=11, window='hanning'):
    """Smooth the data using a window with requested size.

    https://scipy-cookbook.readthedocs.io/items/SignalSmooth.html

    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.

    input:
        x: the input signal
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal

    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)

    See Also

    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter

    TODO: the window parameter could be the window itself if an array instead of a string
    NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
    """
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


if __name__ == '__main__':
    __import__('doctest').testmod()
