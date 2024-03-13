import logging
import sys

logger = logging.getLogger(__name__)

__all__ = ['stream_is_tty', 'stdout_is_tty']


def stream_is_tty(somestream):
    """Check if stream, typically sys.stdout, running in terminal"""
    isatty = getattr(somestream, 'isatty', None)
    return isatty and isatty()


stdout_is_tty = lambda: stream_is_tty(sys.stdout)
