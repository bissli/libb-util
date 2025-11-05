import asyncio
import logging
from concurrent.futures import Future
from functools import partial, wraps
from threading import Thread

logger = logging.getLogger(__name__)

__all__ = [
    'asyncd',
    'call_with_future',
    'threaded',
]


def asyncd(func):
    """Run Synchronous function asynchronously
    https://stackoverflow.com/a/50450553
    """

    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


def call_with_future(fn, future, args, kwargs):
    try:
        result = fn(*args, **kwargs)
        future.set_result(result)
    except Exception as exc:
        future.set_exception(exc)


def threaded(fn):
    """https://stackoverflow.com/a/19846691

    >>> class MyClass:
    ...     @threaded
    ...     def get_my_value(self):
    ...         return 1
    >>> my_obj = MyClass()
    >>> fut = my_obj.get_my_value()  # this will run in a separate thread
    >>> fut.result()  # will block until result is computed
    1
    """

    def wrapper(*args, **kwargs):
        future = Future()
        Thread(target=call_with_future, args=(fn, future, args, kwargs)).start()
        return future

    return wrapper


if __name__ == '__main__':
    __import__('doctest').testmod()
