import os
import signal

import pytest

from libb import SIGNAL_TRANSLATION_MAP, DelayedKeyboardInterrupt


class TestSignalTranslationMap:
    """Tests for SIGNAL_TRANSLATION_MAP."""

    def test_sigint_in_map(self):
        assert signal.SIGINT in SIGNAL_TRANSLATION_MAP
        assert SIGNAL_TRANSLATION_MAP[signal.SIGINT] == 'SIGINT'

    def test_sigterm_in_map(self):
        assert signal.SIGTERM in SIGNAL_TRANSLATION_MAP
        assert SIGNAL_TRANSLATION_MAP[signal.SIGTERM] == 'SIGTERM'


class TestDelayedKeyboardInterrupt:
    """Tests for DelayedKeyboardInterrupt context manager."""

    def test_delayed_keyboard_interrupt_basic(self):
        # Test that the context manager can be entered and exited
        with DelayedKeyboardInterrupt():
            x = 1 + 1
        assert x == 2

    def test_delayed_keyboard_interrupt_propagate_false(self):
        with DelayedKeyboardInterrupt(propagate_to_forked_processes=False):
            result = 'test'
        assert result == 'test'

    def test_delayed_keyboard_interrupt_propagate_true(self):
        with DelayedKeyboardInterrupt(propagate_to_forked_processes=True):
            result = 42
        assert result == 42


class TestDelayedKeyboardInterruptHandler:
    """Tests for signal handler behavior."""

    def test_handler_stores_signal(self, capsys):
        # Test that the handler stores the signal and frame
        dki = DelayedKeyboardInterrupt()
        dki.__enter__()
        dki._old_signal_handler_map = {signal.SIGINT: signal.SIG_DFL, signal.SIGTERM: signal.SIG_DFL}
        # Manually call the handler to simulate receiving a signal
        dki._handler(signal.SIGINT, None)
        assert dki._sig == signal.SIGINT
        assert dki._frame is None
        # Check print output
        captured = capsys.readouterr()
        assert 'SIGINT received' in captured.out
        assert 'delaying' in captured.out
        # Clean up
        for sig in SIGNAL_TRANSLATION_MAP:
            signal.signal(sig, signal.SIG_DFL)

    def test_handler_pid_mismatch_propagate_none(self, capsys, monkeypatch):
        # Test handler with PID mismatch and propagate=None (ignores signal)
        dki = DelayedKeyboardInterrupt(propagate_to_forked_processes=None)
        dki._pid = os.getpid() + 1  # Simulate forked process by changing pid
        dki._old_signal_handler_map = {signal.SIGINT: signal.SIG_DFL, signal.SIGTERM: signal.SIG_DFL}

        # Handler should return early when PID mismatch and propagate=None
        result = dki._handler(signal.SIGINT, None)
        assert result is None  # Returns early
        captured = capsys.readouterr()
        assert 'PID mismatch' in captured.out
        assert 'ignoring the signal' in captured.out

    def test_handler_pid_mismatch_propagate_false(self, capsys):
        # Test handler with PID mismatch and propagate=False (calls original handler)
        dki = DelayedKeyboardInterrupt(propagate_to_forked_processes=False)
        dki._pid = os.getpid() + 1  # Simulate forked process
        called = []

        def mock_handler(sig, frame):
            called.append((sig, frame))
        dki._old_signal_handler_map = {signal.SIGINT: mock_handler, signal.SIGTERM: signal.SIG_DFL}

        dki._handler(signal.SIGINT, None)
        assert len(called) == 1
        assert called[0][0] == signal.SIGINT
        captured = capsys.readouterr()
        assert 'PID mismatch' in captured.out
        assert 'calling original handler' in captured.out

    def test_exit_calls_old_handler_when_signal_received(self, capsys):
        # Test that __exit__ calls the old handler when a signal was received
        called = []

        def mock_handler(sig, frame):
            called.append((sig, frame))

        dki = DelayedKeyboardInterrupt()
        dki._old_signal_handler_map = {signal.SIGINT: mock_handler, signal.SIGTERM: signal.SIG_DFL}
        dki._sig = signal.SIGINT
        dki._frame = None

        # Manually exit - should call the old handler
        dki.__exit__(None, None, None)
        assert len(called) == 1
        assert called[0][0] == signal.SIGINT


if __name__ == '__main__':
    pytest.main([__file__])
