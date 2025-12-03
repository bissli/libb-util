import io
import sys
import tempfile

import pytest

from libb import json_loads_byteified, render_csv, suppress_print
from libb import wrap_suppress_print
from libb.iolib import CsvZip, iterable_to_stream, json_load_byteified, stream
import pathlib


class TestRenderCsv:
    """Tests for render_csv function."""

    def test_render_csv_basic(self):
        rows = [['a', 'b', 'c'], [1, 2, 3]]
        result = render_csv(rows)
        assert 'a,b,c' in result
        assert '1,2,3' in result

    def test_render_csv_empty(self):
        result = render_csv([])
        assert result == ''

    def test_render_csv_single_row(self):
        result = render_csv([['x', 'y', 'z']])
        assert 'x,y,z' in result


class TestJsonLoadsByteified:
    """Tests for json_loads_byteified function."""

    def test_simple_dict(self):
        result = json_loads_byteified('{"foo": "bar"}')
        assert result == {'foo': 'bar'}

    def test_nested_structure(self):
        result = json_loads_byteified('{"foo": "bar", "things": [7, {"qux": "baz"}]}')
        assert result == {'foo': 'bar', 'things': [7, {'qux': 'baz'}]}

    def test_list(self):
        result = json_loads_byteified('[1, 2, 3]')
        assert result == [1, 2, 3]

    def test_string(self):
        result = json_loads_byteified('"hello"')
        assert result == 'hello'


class TestSuppressPrint:
    """Tests for suppress_print context manager."""

    def test_suppress_print_captures_output(self):
        captured = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = captured
        # Now test suppress_print
        sys.stdout = original_stdout
        with suppress_print():
            print('this should be suppressed')
        # After context manager, stdout is restored
        assert sys.stdout == original_stdout

    def test_suppress_print_restores_stdout(self):
        original = sys.stdout
        with suppress_print():
            pass
        assert sys.stdout == original


class TestWrapSuppressPrint:
    """Tests for wrap_suppress_print decorator."""

    def test_wrap_suppress_print_returns_value(self):
        @wrap_suppress_print
        def noisy_func():
            print('noise')
            return 42
        result = noisy_func()
        assert result == 42

    def test_wrap_suppress_print_accepts_args(self):
        @wrap_suppress_print
        def add(a, b):
            print(f'Adding {a} + {b}')
            return a + b
        result = add(3, 4)
        assert result == 7


class TestCsvZip:
    """Tests for CsvZip class."""

    def test_csvzip_writecsv(self):
        csvzip = CsvZip()
        data = [['name', 'value'], ['foo', '1'], ['bar', '2']]
        csvzip.writecsv('test', data)
        csvzip.close()

    def test_csvzip_multiple_files(self):
        csvzip = CsvZip()
        csvzip.writecsv('file1', [['a', 'b'], [1, 2]])
        csvzip.writecsv('file2', [['c', 'd'], [3, 4]])
        csvzip.close()

    def test_csvzip_value_property(self):
        csvzip = CsvZip()
        data = [['name', 'value'], ['foo', '1']]
        csvzip.writecsv('test', data)
        # value property closes and returns bytes
        result = csvzip.value
        assert isinstance(result, bytes)
        assert len(result) > 0


class TestIterableToStream:
    """Tests for iterable_to_stream function."""

    def test_iterable_to_stream_basic(self):
        data = [b'hello', b'world']
        stream = iterable_to_stream(data)
        result = stream.read()
        assert b'hello' in result
        assert b'world' in result

    def test_iterable_to_stream_empty(self):
        data = []
        stream = iterable_to_stream(data)
        result = stream.read()
        assert result == b''

    def test_iterable_to_stream_large_chunks(self):
        # Test with chunks larger than buffer
        data = [b'x' * 1000, b'y' * 1000]
        stream = iterable_to_stream(data, buffer_size=100)
        result = stream.read()
        assert len(result) == 2000


class TestStreamDecorator:
    """Tests for stream decorator."""

    def test_stream_with_string_arg(self):
        @stream
        def read_stream(s):
            return s.read()

        result = read_stream('hello world')
        assert result == 'hello world'

    def test_stream_with_bytes_arg(self):
        @stream
        def read_stream(s):
            return s.read()

        result = read_stream(b'hello bytes')
        assert result == b'hello bytes'

    def test_stream_with_iterable_arg(self):
        @stream
        def read_stream(s):
            return s.read()

        result = read_stream([b'chunk1', b'chunk2'])
        assert b'chunk1' in result
        assert b'chunk2' in result

    def test_stream_with_kwarg(self):
        @stream
        def read_stream(data=None):
            return data.read()

        result = read_stream(data='keyword arg')
        assert result == 'keyword arg'

    def test_stream_no_streamable_raises(self):
        @stream
        def no_streamable(x):
            return x

        with pytest.raises(AttributeError, match='Unsupported'):
            no_streamable(123)


class TestJsonLoadByteified:
    """Tests for json_load_byteified function."""

    def test_json_load_byteified_basic(self):
        json_content = '{"key": "value", "nested": {"a": 1}}'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            f.flush()
            with pathlib.Path(f.name).open() as handle:
                result = json_load_byteified(handle)
        assert result == {'key': 'value', 'nested': {'a': 1}}

    def test_json_load_byteified_with_list(self):
        json_content = '["a", "b", "c"]'
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(json_content)
            f.flush()
            with pathlib.Path(f.name).open() as handle:
                result = json_load_byteified(handle)
        assert result == ['a', 'b', 'c']


if __name__ == '__main__':
    pytest.main([__file__])
