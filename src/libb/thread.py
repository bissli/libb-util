import asyncio
import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from functools import partial, wraps
from threading import Lock, Thread
from typing import Any, Self

from tqdm import tqdm

logger = logging.getLogger(__name__)

__all__ = [
    'asyncd',
    'call_with_future',
    'RateLimitedExecutor',
    'TaskRequest',
    'TaskResponse',
    'threaded',
]


@dataclass
class TaskRequest:
    """Request to process an item with optional ID for tracking.
    """
    item: Any
    id: Any = None


@dataclass
class TaskResponse:
    """Response from processing a request.
    """
    result: Any
    request: TaskRequest
    exception: Exception = None

    @property
    def success(self) -> bool:
        """Check if task completed successfully without exception.
        """
        return self.exception is None


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


class RateLimitedExecutor:
    """Executor with rate limiting that returns Request/Response pairs.

    Provides clean request/response API where every response includes the original
    request for easy result tracking and exception handling.

    Basic usage with automatic request IDs:
        with RateLimitedExecutor(max_workers=10, max_per_second=5, show_progress=True) as executor:
            responses = executor.execute_items(process_fn, items, desc='Processing')
            for response in responses:
                if response.success:
                    print(f"Item {response.request.id}: {response.result}")
                else:
                    print(f"Item {response.request.id} failed: {response.exception}")

    Advanced usage with custom request IDs:
        requests = [TaskRequest(item=x, id=f'custom_{i}') for i, x in enumerate(items)]
        responses = executor.execute(process_fn, requests, desc='Processing')
        result_map = {r.request.id: r.result for r in responses if r.success}
    """

    def __init__(self, max_workers: int = None, max_per_second: float = float('inf'),
                 show_progress: bool = False):
        """Initialize rate-limited executor.

        Args:
            max_workers: Maximum number of concurrent threads
            max_per_second: Maximum calls allowed per second
            show_progress: Whether to display progress bar during execution
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self.max_per_second = max_per_second
        self.show_progress = show_progress
        self._call_times = []
        self._lock = Lock()
        logger.info(f'Initialized RateLimitedExecutor: {max_per_second} req/sec, {max_workers} workers')

    def execute(self, fn: Callable, requests: list[TaskRequest], desc: str = 'Processing',
                unit: str = 'item') -> list[TaskResponse]:
        """Execute function on all requests and return responses in order.

        Args:
            fn: Function that takes request.item and returns a result
            requests: List of TaskRequest objects to process
            desc: Description for progress bar
            unit: Unit name for progress bar

        Returns
            List of TaskResponse objects in same order as requests
        """
        start_time = time.time()
        futures = {}
        for i, request in enumerate(requests):
            future = self.submit(fn, request.item)
            futures[future] = (i, request)

        responses = [None] * len(requests)

        future_iter = as_completed(futures.keys())
        if self.show_progress:
            bar_format = '{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]'
            future_iter = tqdm(future_iter, total=len(futures), desc=desc, unit=unit,
                               bar_format=bar_format)

        for future in future_iter:
            index, request = futures[future]
            try:
                result = future.result()
                responses[index] = TaskResponse(result=result, request=request)
            except Exception as exc:
                responses[index] = TaskResponse(result=None, request=request, exception=exc)

        elapsed = time.time() - start_time
        success_count = sum(1 for r in responses if r.success)
        logger.debug(f'Executed {len(requests)} tasks in {elapsed:.2f}s: {success_count} '
                     f'succeeded, {len(requests) - success_count} failed')

        return responses

    def execute_items(self, fn: Callable, items: list, desc: str = 'Processing',
                      unit: str = 'item') -> list[TaskResponse]:
        """Execute function on items (convenience method with auto-generated request IDs).

        Args:
            fn: Function that takes an item and returns a result
            items: List of items to process
            desc: Description for progress bar
            unit: Unit name for progress bar

        Returns
            List of TaskResponse objects with request.id = index
        """
        requests = [TaskRequest(item=item, id=i) for i, item in enumerate(items)]
        return self.execute(fn, requests, desc=desc, unit=unit)

    def _enforce_rate_limit(self) -> None:
        """Block until rate limit allows another call.
        """
        if self.max_per_second == float('inf'):
            return

        with self._lock:
            now = time.time()
            cutoff_time = now - 1.0
            self._call_times = [t for t in self._call_times if t > cutoff_time]

            if len(self._call_times) >= self.max_per_second:
                sleep_time = 1.0 - (now - self._call_times[0]) + 0.01
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    now = time.time()
                    cutoff_time = now - 1.0
                    self._call_times = [t for t in self._call_times if t > cutoff_time]

            self._call_times.append(now)

    def submit(self, fn, *args, **kwargs) -> Future:
        """Submit a callable to be executed with rate limiting.
        """
        self._enforce_rate_limit()
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        """Shutdown the executor.
        """
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self.shutdown(wait=True)
        return False


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
