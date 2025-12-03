import time

import pytest

from libb import Future


class TestFuture:
    """Tests for Future class."""

    def test_future_basic(self):
        def compute():
            return 42
        f = Future(compute)
        result = f()
        assert result == 42

    def test_future_with_args(self):
        def add(a, b):
            return a + b
        f = Future(add, 3, 4)
        result = f()
        assert result == 7

    def test_future_does_not_block_immediately(self):
        def slow_func():
            time.sleep(0.5)
            return 'done'
        start = time.time()
        f = Future(slow_func)
        elapsed = time.time() - start
        # Should return almost immediately (not wait for slow_func)
        assert elapsed < 0.3
        # But calling f() should wait
        result = f()
        assert result == 'done'

    def test_future_repr(self):
        def compute():
            return 123
        f = Future(compute)
        # Initially working
        assert 'working' in repr(f) or 'Future at' in repr(f)
        # After result
        f()
        assert '123' in repr(f) or 'Future at' in repr(f)

    def test_future_result_is_deepcopy(self):
        def return_list():
            return [1, 2, 3]
        f = Future(return_list)
        result1 = f()
        result2 = f()
        # Results should be equal but not the same object
        assert result1 == result2
        result1.append(4)
        result3 = f()
        assert result3 == [1, 2, 3]  # Original not modified

    def test_future_exception_handling(self):
        def raise_error():
            raise ValueError('test error')
        f = Future(raise_error)
        result = f()
        assert result == 'Exception raised within Future'

    def test_future_waits_for_slow_task(self):
        # Test that __call__ waits when result isn't ready (covers line 58)
        def slow_compute():
            time.sleep(0.5)
            return 'completed'
        f = Future(slow_compute)
        # Immediately call - must wait for result
        start = time.time()
        result = f()
        elapsed = time.time() - start
        assert result == 'completed'
        assert elapsed >= 0.4  # Proves we waited

    def test_future_wait_condition(self):
        """Test multiple concurrent callers to hit the wait() call."""
        import threading

        # Use an event to ensure the function doesn't complete until we say so
        barrier = threading.Event()
        results = []
        errors = []

        def blocking_compute():
            barrier.wait()  # Wait until main thread signals
            return 'done'

        f = Future(blocking_compute)

        def caller():
            try:
                results.append(f())
            except Exception as e:
                errors.append(e)

        # Start multiple caller threads that will all wait
        threads = [threading.Thread(target=caller) for _ in range(5)]
        for t in threads:
            t.start()

        # Give threads time to start waiting
        time.sleep(0.2)

        # Release the blocking function
        barrier.set()

        # Wait for all callers to finish
        for t in threads:
            t.join(timeout=2)

        assert len(results) == 5
        assert all(r == 'done' for r in results)
        assert len(errors) == 0


if __name__ == '__main__':
    pytest.main([__file__])
