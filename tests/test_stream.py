import io
import sys
from unittest import mock

import pytest

from libb import is_tty, stream_is_tty


class TestStreamIsTty:
    """Tests for stream_is_tty function."""

    def test_stream_is_tty_stringio(self):
        # StringIO is not a tty
        stream = io.StringIO()
        assert stream_is_tty(stream) is False

    def test_stream_is_tty_bytesio(self):
        # BytesIO is not a tty
        stream = io.BytesIO()
        assert stream_is_tty(stream) is False

    def test_stream_is_tty_no_isatty(self):
        # Object without isatty method
        class FakeStream:
            pass
        stream = FakeStream()
        result = stream_is_tty(stream)
        assert result is None or result is False


class TestIsTty:
    """Tests for is_tty function."""

    def test_is_tty_returns_bool(self):
        result = is_tty()
        assert isinstance(result, bool)

    def test_is_tty_true_under_pytest(self):
        # Pytest is always considered development mode
        assert is_tty() is True

    def test_is_tty_checks_stderr_not_stdout(self):
        # When not under pytest, should check stderr (not stdout)
        # since logs typically go to stderr
        with mock.patch.dict(sys.modules, {'pytest': None}):
            # Remove pytest from modules to test the fallback path
            modules_without_pytest = {k: v for k, v in sys.modules.items() if k != 'pytest'}
            with mock.patch.dict(sys.modules, modules_without_pytest, clear=True):
                with mock.patch.object(sys.stdin, 'isatty', return_value=True):
                    with mock.patch.object(sys.stderr, 'isatty', return_value=True):
                        with mock.patch.object(sys.stdout, 'isatty', return_value=False):
                            # stdout is False but stderr is True - should return True
                            from libb.stream import is_tty as is_tty_fresh
                            assert is_tty_fresh() is True

    def test_is_tty_false_when_stdin_not_tty(self):
        # When stdin is not a TTY (e.g., piped input), should return False
        modules_without_pytest = {k: v for k, v in sys.modules.items() if k != 'pytest'}
        with mock.patch.dict(sys.modules, modules_without_pytest, clear=True):
            with mock.patch.object(sys.stdin, 'isatty', return_value=False):
                with mock.patch.object(sys.stderr, 'isatty', return_value=True):
                    from libb.stream import is_tty as is_tty_fresh
                    assert is_tty_fresh() is False

    def test_is_tty_false_when_stderr_not_tty(self):
        # When stderr is not a TTY (e.g., redirected), should return False
        modules_without_pytest = {k: v for k, v in sys.modules.items() if k != 'pytest'}
        with mock.patch.dict(sys.modules, modules_without_pytest, clear=True):
            with mock.patch.object(sys.stdin, 'isatty', return_value=True):
                with mock.patch.object(sys.stderr, 'isatty', return_value=False):
                    from libb.stream import is_tty as is_tty_fresh
                    assert is_tty_fresh() is False


if __name__ == '__main__':
    pytest.main([__file__])
