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
    """Check if running in a terminal.

    Returns True if:
    - Running under pytest (always True for testing)
    - stdin is a TTY (interactive input)
    - stderr is a TTY (logger output visible in terminal)

    :returns: True if in a terminal environment.
    :rtype: bool
    """
    if 'pytest' in sys.modules:
        return True
    return stream_is_tty(sys.stdin) and stream_is_tty(sys.stderr)
