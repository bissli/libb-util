
import pytest

from libb import print_exception, try_else


class TestPrintException:
    """Tests for print_exception function."""

    def test_print_exception_short(self, capsys):
        try:
            raise ValueError('test error')
        except ValueError as e:
            print_exception(e, short=True)
        captured = capsys.readouterr()
        assert 'traceback above the current stack frame' in captured.out.lower()
        assert 'ValueError' in captured.out

    def test_print_exception_long(self, capsys):
        try:
            raise RuntimeError('full trace test')
        except RuntimeError as e:
            print_exception(e, short=False)
        captured = capsys.readouterr()
        assert 'full traceback' in captured.out.lower()
        assert 'RuntimeError' in captured.out


class TestTryElse:
    """Tests for try_else function."""

    def test_try_else_success(self):
        # try_else wraps a function and returns a callable
        safe_int = try_else(int, default=0)
        result = safe_int('42')
        assert result == 42

    def test_try_else_exception(self):
        safe_int = try_else(int, default=-1)
        result = safe_int('not a number')
        assert result == -1

    def test_try_else_with_callable_default(self):
        # Default can be callable - receives same args
        fallback = lambda x: f'failed: {x}'
        safe_int = try_else(int, default=fallback)
        result = safe_int('bad')
        assert result == 'failed: bad'


if __name__ == '__main__':
    pytest.main([__file__])
