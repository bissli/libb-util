"""Geographic utilities for coordinate transformations"""

import logging
import math

logger = logging.getLogger(__name__)

__all__ = [
    'merc_x',
    'merc_y',
]


def merc_x(lon, r_major=6378137.0):
    """Project longitude into mercator / radians from major axis.

    :param float lon: Longitude in degrees.
    :param float r_major: Major axis radius in meters (default: Earth WGS84).
    :returns: Mercator x coordinate.
    :rtype: float

    Example::

        >>> "{:0.3f}".format(merc_x(40.7484))
        '4536091.139'
    """
    return r_major * math.radians(lon)


def merc_y(lat, r_major=6378137.0, r_minor=6356752.3142):
    """Project latitude into mercator / radians from major/minor axes.

    :param float lat: Latitude in degrees.
    :param float r_major: Major axis radius in meters (default: Earth WGS84).
    :param float r_minor: Minor axis radius in meters (default: Earth WGS84).
    :returns: Mercator y coordinate.
    :rtype: float

    Example::

        >>> "{:0.3f}".format(merc_y(73.9857))
        '12468646.871'
    """
    lat = min(lat, 89.5)
    lat = max(lat, -89.5)
    eccent = math.sqrt(1 - (r_minor / r_major) ** 2)
    phi = math.radians(lat)
    sinphi = math.sin(phi)
    con = eccent * sinphi
    com = eccent / 2
    den = ((1.0 - con) / (1.0 + con)) ** com
    ts = math.tan((math.pi / 2 - phi) / 2) / den
    y = 0.0 - r_major * math.log(ts)
    return y


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
