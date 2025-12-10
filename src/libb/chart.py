import logging
import math
from io import BytesIO

logger = logging.getLogger(__name__)

__all__ = ['numpy_timeseries_plot']


class NiceScale:
    """Calculate nice axis scale values for charts.

    The "nicest" numbers in decimal are 1, 2, and 5, and all power-of-ten
    multiples of these numbers. This class uses only such numbers for tick
    spacing and places tick marks at multiples of the tick spacing.

    :param float minv: Minimum value of the data range.
    :param float maxv: Maximum value of the data range.

    Example::

        >>> scale = NiceScale(0.5, 10.5)
        >>> scale.nice_min
        0.0
        >>> scale.nice_max
        12.0
        >>> scale.tick_spacing
        2.0

    .. note::
        Algorithm from https://stackoverflow.com/a/16363437
    """

    def __init__(self, minv, maxv):
        self.max_ticks = 8
        self.tick_spacing = 0
        self.lst = 10
        self.nice_min = 0
        self.nice_max = 0
        self.min_point = minv
        self.max_point = maxv
        self.calculate()

    def calculate(self):
        self.lst = self.nice_num(self.max_point - self.min_point, False)
        self.tick_spacing = self.nice_num(self.lst / (self.max_ticks - 1), True)
        self.nice_min = math.floor(self.min_point / self.tick_spacing) * self.tick_spacing
        self.nice_max = math.ceil(self.max_point / self.tick_spacing) * self.tick_spacing

    def nice_num(self, lst, rround):
        self.lst = lst
        if self.lst <= 0:
            return 1
        exponent = math.floor(math.log10(self.lst))
        fraction = self.lst / math.pow(10, exponent)
        if rround:
            if fraction < 1.5:
                nice_fraction = 1
            elif fraction < 3:
                nice_fraction = 2
            elif fraction < 7:
                nice_fraction = 5
            else:
                nice_fraction = 10
        else:
            if fraction <= 1:
                nice_fraction = 1
            elif fraction <= 2:
                nice_fraction = 2
            elif fraction <= 5:
                nice_fraction = 5
            else:
                nice_fraction = 10
        return nice_fraction * math.pow(10, exponent)


DEFAULT_TIMESERIES_COLORS = (
    'tab:blue',
    'tab:green',
    'tab:orange',
    'tab:red',
    'tab:olive',
)


def numpy_timeseries_plot(title, dates, series=None, labels=None, formats=None):
    """Create a matplotlib timeseries plot with automatic subplot layout.

    The layout adapts based on the number of series:

    - 1 series: single plot
    - 2 series: same plot with dual y-axes (overlapping)
    - 3+ series: stacked vertically as subplots

    :param str title: Plot title.
    :param dates: Array of dates for x-axis.
    :param list series: List of y-value arrays.
    :param list labels: Labels for each series.
    :param list formats: Formatter functions for each y-axis.
    :returns: BytesIO buffer containing the PNG image.
    :rtype: BytesIO
    """
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick
    import numpy as np
    from matplotlib import dates as mpl_dates

    if formats is None:
        formats = []
    if labels is None:
        labels = []
    if series is None:
        series = []
    plt.rcParams['figure.figsize'] = (6.4 * 1.5, 4.8 * 1.5)
    numy = len(series)
    assert numy == len(labels) == len(formats)
    dates = np.array(dates)
    if numy <= 2:
        fig, axes = plt.subplots(1)
        axes = [axes]
    else:
        fig, axes = plt.subplots(numy)
        axes = list(axes)
    colors = (c for c in DEFAULT_TIMESERIES_COLORS)
    ax = None
    for ts, lbl, fmt in zip(series, labels, formats):
        ts = np.array(ts)
        if ax is None or numy > 2:
            ax = axes.pop(0)
        elif numy <= 2:
            ax = ax.twinx()
        mask = np.isfinite(ts)
        color = next(colors)
        try:
            ax.plot(dates[mask], ts[mask], color=color)
        except Exception as exc:
            logger.warning(exc)
            continue
        ax.tick_params(axis='y', labelcolor=color)
        if numy > 2:
            ax.title.set_text(lbl)
            ax.grid(True)
            t = NiceScale(min(ts[mask]), max(ts[mask]))
            ax.set_yticks(np.arange(t.nice_min, t.nice_max, t.tick_spacing))
        else:
            ax.set_ylabel(lbl)
            plt.title(title)
        ax.yaxis.set_major_formatter(mtick.FuncFormatter(fmt))
        ax.xaxis.set_major_formatter(mpl_dates.DateFormatter('%m/%d/%y'))
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format='png')
    plt.clf()
    plt.rcParams['figure.figsize'] = plt.rcParamsDefault['figure.figsize']
    return buf
