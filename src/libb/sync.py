import datetime
import math
import signal
import threading
import time
import warnings
from collections.abc import Callable
from datetime import timedelta, timezone
from typing import Any, TypeVar, cast

__all__ = [
    'syncd',
    'NonBlockingDelay',
    'delay',
    'debounce',
    'wait_until',
    'timeout',
]


def syncd(lock):
    """Synchronize an arbitrary number of functions with shared lock
    yanked out of the python decorator wiki, adding an illustrative test

    >>> import time
    >>> from threading import Lock, Thread
    >>> from queue import Queue
    >>> lock = Lock()
    >>> A = Queue()
    >>> A.put('b')

    >>> @syncd(lock)
    ... def alpha():
    ...     time.sleep(2)
    ...     A.put('a')

    >>> @syncd(lock)
    ... def omega():
    ...     return A.get()

    >>> a = Thread(target=alpha)
    >>> a.start()
    >>> A.empty()
    False
    >>> A.get()
    'b'
    >>> A.empty()
    True
    >>> omega()  # 2-second blocking comes here
    'a'
    """
    def wrap(f):
        def new_function(*args, **kw):
            lock.acquire()
            try:
                return f(*args, **kw)
            finally:
                lock.release()
        return new_function
    return wrap


class NonBlockingDelay:
    """Non blocking delay class"""

    def __init__(self):
        self._timestamp = 0.0
        self._delay = 0.0

    def timeout(self):
        """Check if time is up"""
        return (time.monotonic() - self._timestamp) > self._delay

    def delay(self, delay: float) -> None:
        """Non blocking delay in seconds"""
        self._timestamp = time.monotonic()
        self._delay = delay


def delay(seconds: float) -> None:
    """Delay non-blocking for N seconds (busy-wait).

    .. deprecated::
        Use time.sleep() for efficient blocking delays. This function is kept for backward compatibility.
    """
    warnings.warn(
        'delay() is deprecated, use time.sleep() instead',
        DeprecationWarning,
        stacklevel=2
    )
    d = NonBlockingDelay()
    d.delay(seconds)
    while not d.timeout():
        continue


class Debouncer:
    """Debounce handler for `debounce`"""

    def __init__(self, func: Callable[..., Any], wait: float):
        self.func = func
        self.wait = wait
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()
        self._last_args = None
        self._last_kwargs = None

    def __call__(self, *args, **kwargs) -> None:
        with self._lock:
            self._last_args = args
            self._last_kwargs = kwargs
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.wait, self.func, args, kwargs)
            self._timer.start()

    def flush(self) -> None:
        """Execute pending call immediately if one exists."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
                if self._last_args is not None:
                    self.func(*self._last_args, **self._last_kwargs)
                    self._last_args = None
                    self._last_kwargs = None

    def cancel(self) -> None:
        """Cancel any pending call without executing."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._last_args = None
            self._last_kwargs = None


VoidFunction = TypeVar('VoidFunction', bound=Callable[..., None])


def debounce(wait: float):
    """Wait `interval` seconds before calling `func`, and cancel
    if called again. When a function is called multiple times with
    debounce it will only return once if within `wait` window.

    >>> @debounce(1)
    ... def hi(name):
    ...     print('hi {}'.format(name))

    >> hi('foo')
    >> time.sleep(0.5)
    >> hi('bar')
    >> time.sleep(0.5)
    >> hi('baz')

    """
    def wrapper(func: VoidFunction) -> VoidFunction:
        if wait <= 0:
            return func
        return cast(VoidFunction, Debouncer(func, wait))
    return wrapper


def wait_until(hour, minute=0, second=0, tz=timezone.utc, time_unit='milliseconds') -> int:
    """Hour/minute `until` which to sleep, ex hour=17 means sleep utill 5PM

    >>> from unittest.mock import patch

    >>> with patch(f'{__name__}.datetime', wraps=datetime) as mock:
    ...     mock.datetime.now.return_value = datetime.datetime(2000, 5, 1, 17, 30, 0, 0, tzinfo=timezone.utc)
    ...     f"{wait_until(12, 0, 0)/3600/1000:.1f} hours"
    '18.5 hours'

    >>> with patch(f'{__name__}.datetime', wraps=datetime) as mock:
    ...     mock.datetime.now.return_value = datetime.datetime(2000, 7, 1, 17, 15, 0, 0, tzinfo=timezone.utc)
    ...     f"{wait_until(17, 45, 0)/3600/1000:.1f} hours"
    '0.5 hours'

    >>> with patch(f'{__name__}.datetime', wraps=datetime) as mock:
    ...     mock.datetime.now.return_value = datetime.datetime(2000, 11, 1, 17, 15, 0, 0, tzinfo=timezone.utc)
    ...     f"{wait_until(16, 15, 0)/3600/1000:.1f} hours"
    '23.0 hours'
    """
    assert time_unit in {'seconds', 'milliseconds'}
    this = datetime.datetime.now(tz=tz)
    then = datetime.datetime(this.year, this.month, this.day, hour, minute, second, tzinfo=tz)
    if this >= then:
        then += timedelta(days=1)
    return math.ceil((then - this).seconds) * (1000 if time_unit == 'milliseconds' else 1)


class timeout:
    """with statement to manage timeouts for potential hanging code
    http://stackoverflow.com/a/22348885/424380

    >>> import time
    >>> with timeout(1):
    ...     time.sleep(2)
    ...     print("foo")
    Traceback (most recent call last):
        ...
    OSError: Timeout!!
    >>> with timeout(1):
    ...     print("foo")
    foo
    """

    def __init__(self, seconds=100, error_message='Timeout!!'):
        self.seconds = seconds
        self.error_message = error_message

    def handle_timeout(self, signum, frame):
        raise OSError(self.error_message)

    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)

    def __exit__(self, type, value, traceback):
        signal.alarm(0)


if __name__ == '__main__':
    __import__('doctest').testmod()
