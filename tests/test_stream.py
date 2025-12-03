import io

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
        # In test environment, usually not a tty
        result = is_tty()
        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__])
