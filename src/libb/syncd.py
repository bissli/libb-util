import time


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


if __name__ == '__main__':
    __import__('doctest').testmod()
