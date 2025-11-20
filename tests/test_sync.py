import signal
import time
from queue import Queue
from threading import Lock, Thread
from unittest.mock import patch

import pytest

from libb import NonBlockingDelay, debounce, syncd, timeout, wait_until
from libb.sync import datetime


def test_nonblocking_delay_timeout():
    """Verify NonBlockingDelay.timeout() correctly detects when delay period has passed.
    """
    delay = NonBlockingDelay()

    assert delay.timeout()

    delay.delay(0.1)
    assert not delay.timeout()

    time.sleep(0.15)
    assert delay.timeout()


def test_nonblocking_delay_precision():
    """Verify NonBlockingDelay uses monotonic time for better precision.
    """
    delay = NonBlockingDelay()

    delay.delay(0.05)
    start = time.monotonic()

    while not delay.timeout():
        time.sleep(0.01)

    elapsed = time.monotonic() - start
    assert 0.05 <= elapsed < 0.1


def test_multiple_nonblocking_delays():
    """Verify multiple NonBlockingDelay instances can run independently.
    """
    d1 = NonBlockingDelay()
    d2 = NonBlockingDelay()

    d1.delay(0.1)
    d2.delay(0.2)

    assert not d1.timeout()
    assert not d2.timeout()

    time.sleep(0.15)
    assert d1.timeout()
    assert not d2.timeout()

    time.sleep(0.1)
    assert d1.timeout()
    assert d2.timeout()


def test_nonblocking_delay_zero():
    """Verify NonBlockingDelay with zero delay times out immediately.
    """
    delay = NonBlockingDelay()
    delay.delay(0)
    assert delay.timeout()


def test_nonblocking_delay_restart():
    """Verify NonBlockingDelay can be restarted with a new delay.
    """
    delay = NonBlockingDelay()

    delay.delay(0.1)
    time.sleep(0.05)
    assert not delay.timeout()

    delay.delay(0.1)
    time.sleep(0.08)
    assert not delay.timeout()

    time.sleep(0.05)
    assert delay.timeout()


def test_delay_function_with_deprecation_warning():
    """Verify delay() function works but emits deprecation warning.
    """
    import warnings

    from libb import delay

    start = time.monotonic()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('always')
        delay(0.1)

        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert 'delay() is deprecated' in str(w[0].message)
        assert 'time.sleep()' in str(w[0].message)

    elapsed = time.monotonic() - start
    assert 0.1 <= elapsed < 0.2


def test_syncd_lock_synchronization():
    """Verify syncd decorator synchronizes functions with shared lock.
    """
    lock = Lock()
    queue = Queue()
    queue.put('b')

    @syncd(lock)
    def alpha():
        time.sleep(0.2)
        queue.put('a')

    @syncd(lock)
    def omega():
        return queue.get()

    thread = Thread(target=alpha)
    thread.start()

    assert not queue.empty()
    assert queue.get() == 'b'
    assert queue.empty()
    assert omega() == 'a'
    thread.join()


def test_syncd_exception_handling():
    """Verify syncd decorator releases lock even when wrapped function raises exception.
    """
    lock = Lock()
    results = []

    @syncd(lock)
    def failing_func():
        results.append('started')
        raise ValueError('test error')

    @syncd(lock)
    def normal_func():
        results.append('normal')

    with pytest.raises(ValueError, match='test error'):
        failing_func()

    normal_func()
    assert results == ['started', 'normal']
    assert not lock.locked()


def test_syncd_return_value():
    """Verify syncd decorator preserves function return values.
    """
    lock = Lock()

    @syncd(lock)
    def get_value(x, y):
        return x + y

    assert get_value(10, 20) == 30
    assert get_value('foo', 'bar') == 'foobar'


def test_debounce_delays_execution():
    """Verify debounce decorator delays function execution until wait period expires.
    """
    results = []

    @debounce(0.1)
    def record(value):
        results.append(value)

    record('foo')
    time.sleep(0.05)
    record('bar')
    time.sleep(0.05)
    record('baz')

    assert len(results) == 0

    time.sleep(0.15)
    assert results == ['baz']


def test_debounce_with_zero_wait():
    """Verify debounce with zero wait executes immediately without delay.
    """
    results = []

    @debounce(0)
    def record(value):
        results.append(value)

    record('immediate')
    assert results == ['immediate']


def test_debounce_flush():
    """Verify debounce flush() executes pending call immediately.
    """
    results = []

    @debounce(0.2)
    def record(value):
        results.append(value)

    record('pending')
    assert len(results) == 0

    record.flush()
    assert results == ['pending']

    time.sleep(0.3)
    assert results == ['pending']


def test_debounce_cancel():
    """Verify debounce cancel() cancels pending call without executing.
    """
    results = []

    @debounce(0.2)
    def record(value):
        results.append(value)

    record('cancelled')
    assert len(results) == 0

    record.cancel()

    time.sleep(0.3)
    assert len(results) == 0


def test_debounce_multiple_calls():
    """Verify debounce only executes last call after multiple rapid calls.
    """
    results = []

    @debounce(0.1)
    def record(value):
        results.append(value)

    record('first')
    record('second')
    record('third')

    assert len(results) == 0

    time.sleep(0.15)
    assert results == ['third']


def test_wait_until_next_day():
    """Verify wait_until calculates time to next day when target time has passed.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 5, 1, 17, 30, 0, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(12, 0, 0)
        hours = result / 3600 / 1000
        assert 18.4 < hours < 18.6


def test_wait_until_same_day():
    """Verify wait_until calculates time to same day when target time is ahead.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 7, 1, 17, 15, 0, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(17, 45, 0)
        hours = result / 3600 / 1000
        assert 0.4 < hours < 0.6


def test_wait_until_previous_hour():
    """Verify wait_until calculates time to next day when hour has passed today.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 11, 1, 17, 15, 0, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(16, 15, 0)
        hours = result / 3600 / 1000
        assert 22.9 < hours < 23.1


def test_wait_until_seconds_unit():
    """Verify wait_until returns correct value when time_unit is seconds.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 7, 1, 17, 15, 0, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(17, 45, 0, time_unit='seconds')
        assert 1800 == result


def test_wait_until_uses_total_seconds():
    """Verify wait_until uses total_seconds() not seconds attribute.

    This test ensures the function correctly handles time differences that
    span multiple days. The .seconds attribute only returns 0-86399, while
    .total_seconds() includes the full duration.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 1, 1, 23, 59, 59, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(0, 0, 0, time_unit='seconds')
        assert result == 1


def test_wait_until_midnight_crossover():
    """Verify wait_until correctly calculates time across midnight boundary.
    """
    with patch('libb.sync.datetime', wraps=datetime) as mock:
        mock.datetime.now.return_value = datetime.datetime(2000, 12, 31, 23, 0, 0, 0, tzinfo=datetime.timezone.utc)
        result = wait_until(1, 0, 0, time_unit='seconds')
        assert result == 7200


def test_wait_until_invalid_hour():
    """Verify wait_until raises ValueError for invalid hour values.
    """
    with pytest.raises(ValueError, match='hour must be between 0 and 23'):
        wait_until(24)

    with pytest.raises(ValueError, match='hour must be between 0 and 23'):
        wait_until(-1)


def test_wait_until_invalid_minute():
    """Verify wait_until raises ValueError for invalid minute values.
    """
    with pytest.raises(ValueError, match='minute must be between 0 and 59'):
        wait_until(12, 60)

    with pytest.raises(ValueError, match='minute must be between 0 and 59'):
        wait_until(12, -1)


def test_wait_until_invalid_second():
    """Verify wait_until raises ValueError for invalid second values.
    """
    with pytest.raises(ValueError, match='second must be between 0 and 59'):
        wait_until(12, 30, 60)

    with pytest.raises(ValueError, match='second must be between 0 and 59'):
        wait_until(12, 30, -1)


def test_timeout_raises_error():
    """Verify timeout context manager raises OSError when time limit is exceeded.
    """
    with pytest.raises(OSError, match='Timeout!!'), timeout(1):
        time.sleep(2)


def test_timeout_allows_completion():
    """Verify timeout context manager allows code to complete within time limit.
    """
    result = []
    with timeout(1):
        result.append('completed')
    assert result == ['completed']


def test_timeout_restores_signal_handler():
    """Verify timeout context manager restores previous SIGALRM handler.
    """
    def custom_handler(signum, frame):
        pass

    original_handler = signal.signal(signal.SIGALRM, custom_handler)

    try:
        with timeout(10):
            pass

        current_handler = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        assert current_handler == custom_handler
    finally:
        signal.signal(signal.SIGALRM, original_handler)


def test_timeout_custom_error_message():
    """Verify timeout context manager uses custom error message.
    """
    with pytest.raises(OSError, match='Custom timeout message'):
        with timeout(1, error_message='Custom timeout message'):
            time.sleep(2)


def test_timeout_with_exception():
    """Verify timeout context manager allows exceptions to propagate normally.
    """
    with pytest.raises(ValueError, match='test error'), timeout(10):
        raise ValueError('test error')


if __name__ == '__main__':
    __import__('pytest').main([__file__])
