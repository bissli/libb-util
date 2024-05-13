import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

__all__ = [
    'syncd',
    'NonBlockingDelay',
    'delay',
    'debounce',
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
        self._timestamp = 0
        self._delay = 0

    def _seconds(self):
        return int(time.time())

    def timeout(self):
        """Check if time is up"""
        return (self._seconds() - self._timestamp) > self._delay

    def delay(self, delay):
        """Non blocking delay in seconds"""
        self._timestamp = self._seconds()
        self._delay = delay


def delay(seconds):
    """Delay non-blocking for N seconds
    """
    delay = NonBlockingDelay()
    delay.delay(seconds)
    while not delay.timeout():
        continue


class Debouncer:
    """Debounce handler for `debounce`
    """
    def __init__(self, func: Callable[..., Any], wait: float):
        self.func = func
        self.wait = wait
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs) -> None:
        with self._lock:
            # if called again cancel current timer and restart
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.wait, self.func, args, kwargs)
            self._timer.start()


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


if __name__ == '__main__':
    __import__('doctest').testmod()
