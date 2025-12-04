import copy
from threading import Condition, Thread

__all__ = [
    'Future',
]


class Future:
    """Easy threading via a Future pattern.

    Runs a time-consuming function in a separate thread while allowing
    the main thread to continue uninterrupted.

    :param func: Function to run in background thread.
    :param param: Arguments to pass to the function.

    .. note::
        Algorithm from http://code.activestate.com/recipes/84317/

    Example::

        >>> import time, math
        >>> def wait_and_add(x):
        ...     time.sleep(2)
        ...     return x+1

    Won't wait 2 seconds here::

        >>> start = time.time()
        >>> z = Future(wait_and_add, 2)
        >>> 1+2
        3
        >>> int(math.ceil(time.time()-start))
        1

    At this point we need to wait the 2 seconds::

        >>> z()
        3
        >>> int(math.ceil(time.time()-start)) >= 2
        True
    """

    def __init__(self, func, *param):
        # Constructor
        self.__done = 0
        self.__result = None
        self.__status = 'working'

        # Notify on this Condition when result is ready
        self.__C = Condition()

        # Run the actual function in a separate thread
        self.__T = Thread(target=self.Wrapper, args=(func, param))
        self.__T.name = 'FutureThread'
        self.__T.start()

    def __repr__(self):
        return '<Future at ' + hex(id(self)) + ':' + self.__status + '>'

    def __call__(self):
        self.__C.acquire()
        while self.__done == 0:
            self.__C.wait()
        self.__C.release()
        # We deepcopy __result to prevent accidental tampering with it.
        a = copy.deepcopy(self.__result)
        return a

    def Wrapper(self, func, param):
        # Run the actual function OUTSIDE the lock so callers can wait
        try:
            result = func(*param)
        except:
            result = 'Exception raised within Future'

        # Only hold lock when updating shared state and notifying
        self.__C.acquire()
        self.__result = result
        self.__done = 1
        self.__status = repr(self.__result)
        self.__C.notify_all()
        self.__C.release()


if __name__ == '__main__':
    __import__('doctest').testmod()
