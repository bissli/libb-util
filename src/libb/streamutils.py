import logging
import sys

logger = logging.getLogger(__name__)

__all__ = ['is_tty', 'stream_is_tty']


def stream_is_tty(somestream):
    """Check if stream, typically sys.stdout, running in terminal"""
    isatty = getattr(somestream, 'isatty', None)
    return isatty and isatty()



def is_tty():
    """Check if the script is running in an interactive terminal.
    """
    return sys.stdin.isatty() and sys.stdout.isatty()
