import logging
import sys

logger = logging.getLogger(__name__)

__all__ = ['is_tty', 'stream_is_tty']


def stream_is_tty(somestream):
    """Check if a stream is running in a terminal.

    :param somestream: Stream to check (typically sys.stdout).
    :returns: True if stream is a TTY.
    :rtype: bool

    Example::

        >>> import io
        >>> stream_is_tty(io.StringIO())
        False
    """
    isatty = getattr(somestream, 'isatty', None)
    return isatty and isatty()



def is_tty():
    """Check if running in an interactive terminal.

    :returns: True if both stdin and stdout are TTYs.
    :rtype: bool
    """
    return sys.stdin.isatty() and sys.stdout.isatty()
