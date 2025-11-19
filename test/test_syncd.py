import time

from libb import NonBlockingDelay


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


def test_delay_function_with_deprecation_warning():
    """Verify delay() function works but emits deprecation warning.
    """
    import warnings
    from libb import delay
    
    start = time.monotonic()
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        delay(0.1)
        
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "delay() is deprecated" in str(w[0].message)
        assert "time.sleep()" in str(w[0].message)
    
    elapsed = time.monotonic() - start
    assert 0.1 <= elapsed < 0.2


if __name__ == '__main__':
    __import__('pytest').main([__file__])
