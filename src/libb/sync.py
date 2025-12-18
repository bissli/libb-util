from __future__ import annotations

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
    """Decorator to synchronize functions with a shared lock.

    :param lock: Threading lock to acquire during function execution.
    :returns: Decorator function.

    Example::

        >>> import threading
        >>> lock = threading.Lock()
        >>> @syncd(lock)
        ... def safe_increment(counter):
        ...     return counter + 1
        >>> safe_increment(0)
        1
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
    """Non-blocking delay for checking time elapsed."""

    def __init__(self):
        self._timestamp = 0.0
        self._delay = 0.0

    def timeout(self):
        """Check if the delay time has elapsed.

        :returns: True if time is up.
        :rtype: bool
        """
        return (time.monotonic() - self._timestamp) > self._delay

    def delay(self, delay: float) -> None:
        """Start a non-blocking delay.

        :param float delay: Delay duration in seconds.
        """
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
    """Debounce handler used by :func:`debounce` decorator."""

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
        """Execute any pending call immediately."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
                if self._last_args is not None:
                    self.func(*self._last_args, **self._last_kwargs)
                    self._last_args = None
                    self._last_kwargs = None

    def cancel(self) -> None:
        """Cancel any pending call without executing it."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self._last_args = None
            self._last_kwargs = None


VoidFunction = TypeVar('VoidFunction', bound=Callable[..., None])


def debounce(wait: float):
    """Decorator to debounce function calls.

    Waits ``wait`` seconds before calling function, cancels if called again.

    :param float wait: Seconds to wait before executing.
    :returns: Decorator function.
    """
    def wrapper(func: VoidFunction) -> VoidFunction:
        if wait <= 0:
            return func
        return cast(VoidFunction, Debouncer(func, wait))
    return wrapper


def wait_until(
    hour: int,
    minute: int = 0,
    second: int = 0,
    tz: datetime.tzinfo | None = timezone.utc,
    time_unit: str = 'milliseconds'
) -> int:
    """Calculate time to wait until specified hour/minute/second.

    :param int hour: Hour (0-23).
    :param int minute: Minute (0-59).
    :param int second: Second (0-59).
    :param tz: Timezone (default: UTC).
    :param str time_unit: Return unit ('seconds' or 'milliseconds').
    :returns: Time to wait in specified unit.
    :rtype: int
    :raises ValueError: If hour/minute/second out of range.
    """
    assert time_unit in {'seconds', 'milliseconds'}
    if not (0 <= hour <= 23):
        raise ValueError(f'hour must be between 0 and 23, got {hour}')
    if not (0 <= minute <= 59):
        raise ValueError(f'minute must be between 0 and 59, got {minute}')
    if not (0 <= second <= 59):
        raise ValueError(f'second must be between 0 and 59, got {second}')
    this = datetime.datetime.now(tz=tz)
    then = datetime.datetime(this.year, this.month, this.day, hour, minute, second, tzinfo=tz)
    if this >= then:
        then += timedelta(days=1)
    return math.ceil((then - this).total_seconds()) * (1000 if time_unit == 'milliseconds' else 1)


class timeout:
    """Context manager for timing out potentially hanging code.

    :param int seconds: Timeout in seconds (default: 100).
    :param str error_message: Message for timeout error.

    .. warning::
        Uses SIGALRM and only works on Unix/Linux systems.
    """

    def __init__(self, seconds: int = 100, error_message: str = 'Timeout!!'):
        self.seconds = seconds
        self.error_message = error_message
        self._previous_handler = None

    def handle_timeout(self, signum, frame):
        raise OSError(self.error_message)

    def __enter__(self):
        self._previous_handler = signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
        return self

    def __exit__(self, type, value, traceback):
        signal.alarm(0)
        if self._previous_handler is not None:
            signal.signal(signal.SIGALRM, self._previous_handler)
        return False
