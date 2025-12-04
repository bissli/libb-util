import csv
import io
import json
import logging
import os
import pathlib
import sys
from collections.abc import Iterable
from contextlib import contextmanager
from functools import wraps
from zipfile import ZipFile, ZipInfo

logger = logging.getLogger(__name__)

__all__ = [
    'render_csv',
    'CsvZip',
    'iterable_to_stream',
    'stream',
    'json_load_byteified',
    'json_loads_byteified',
    'suppress_print',
    'wrap_suppress_print',
]


def render_csv(rows, dialect=csv.excel):
    """Render rows as CSV string.

    :param rows: Iterable of rows to render.
    :param dialect: CSV dialect to use (default: csv.excel).
    :returns: CSV formatted string.
    :rtype: str

    Example::

        >>> render_csv([['a', 'b'], ['1', '2']])
        'a,b\\r\\n1,2\\r\\n'
    """
    f = io.StringIO()
    writer = csv.writer(f, dialect=dialect)
    for row in rows:
        writer.writerow(row)
    return f.getvalue()


class CsvZip(ZipFile):
    """Zipped CSV file that handles file permissions correctly on DOS.

    Example::

        >>> cz = CsvZip()
        >>> cz.writecsv('test', [['a', 'b'], ['1', '2']])
        >>> len(cz.value) > 0
        True

    .. note::
        See http://stackoverflow.com/q/279945/424380
    """

    @property
    def value(self):
        self.close()
        return self.__buffer.getvalue()

    def __init__(self):
        self.__buffer = io.BytesIO()
        ZipFile.__init__(self, self.__buffer, 'w')

    def writecsv(self, filename, data):
        info = ZipInfo(f'{filename}.csv')
        info.external_attr = 0o644 << 16
        self.writestr(info, render_csv(data).encode('utf-8'))


def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """Convert an iterable that yields bytestrings to a read-only input stream.

    :param iterable: Iterable yielding bytestrings.
    :param int buffer_size: Buffer size for the stream.
    :returns: BufferedReader stream.

    Example::

        >>> stream = iterable_to_stream([b'hello', b' ', b'world'])
        >>> stream.read()
        b'hello world'

    .. note::
        See https://stackoverflow.com/a/20260030
    """

    class IterStream(io.RawIOBase):
        def __init__(self):
            self.leftover = None
            self.iterable = iter(iterable)

        def readable(self):
            return True

        def readinto(self, b):
            try:
                l = len(b)
                chunk = self.leftover or next(self.iterable)
                output, self.leftover = chunk[:l], chunk[l:]
                b[: len(output)] = output
                return len(output)
            except StopIteration:
                return 0

    return io.BufferedReader(IterStream(), buffer_size=buffer_size)


def stream(func):
    """Decorator that converts first streamable input param to a stream.

    :param func: Function to wrap.
    :returns: Wrapped function.
    """

    class StreamWriter:
        """Find `first` streamable argument in params and convert to stream"""

        def __init__(self, *args, **kwargs):
            self.types = (str, bytes, Iterable) + (str,)
            for i, arg in enumerate(args):
                if isinstance(arg, self.types):
                    self.idx = i
                    self.key = None
                    self.val = arg
                    return
            for k, v in list(kwargs.items()):
                if isinstance(v, self.types):
                    self.idx = None
                    self.key = k
                    self.val = v
                    return
            raise AttributeError('Unsupported Params')

        def convert(self):
            val = self.val
            if isinstance(val, str):
                return io.StringIO(val)
            elif isinstance(val, (bytes,)):
                return io.BytesIO(val)
            elif isinstance(val, Iterable):
                return iterable_to_stream(val)

    @wraps(func)
    def wrapper(*args, **kwargs):
        sw = StreamWriter(*args, **kwargs)
        s = sw.convert()
        if sw.idx is not None:
            args = list(args)
            args[sw.idx] = s
        else:
            kwargs[sw.key] = s
        return func(*args, **kwargs)

    return wrapper


#
# handle generating ascii-encoded json where necessary
#


def json_load_byteified(file_handle):
    """Parse ASCII encoded JSON from file handle.

    :param file_handle: File handle to read from.
    :returns: Parsed JSON data.
    """
    return _byteify(json.load(file_handle, object_hook=_byteify), ignore_dicts=True)


def json_loads_byteified(json_text):
    """Parse ASCII encoded JSON from text string.

    :param str json_text: JSON text to parse.
    :returns: Parsed JSON data.

    Example::

        >>> json_loads_byteified('{"foo": "bar"}')
        {'foo': 'bar'}
        >>> json_loads_byteified('{"foo": "bar", "things": [7, {"qux": "baz", "moo": {"cow": ["milk"]}}]}')
        {'foo': 'bar', 'things': [7, {'qux': 'baz', 'moo': {'cow': ['milk']}}]}
    """
    return _byteify(json.loads(json_text, object_hook=_byteify), ignore_dicts=True)


def _byteify(data, ignore_dicts=False):
    """Recursively convert JSON data to native Python types.

    :param data: JSON data to convert.
    :param bool ignore_dicts: If True, skip dictionary conversion.
    :returns: Converted data.
    """
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True) for key, value in list(data.items())
        }
    return data


@contextmanager
def suppress_print():
    """Context manager to suppress stdout (print statements).

    Useful when third-party code includes unwanted print statements.

    Example::

        >>> with suppress_print():
        ...     print("This won't appear")
    """
    try:
        _original_stdout = sys.stdout
        sys.stdout = pathlib.Path(os.devnull).open('w')
        yield
    finally:
        sys.stdout.close()
        sys.stdout = _original_stdout


def wrap_suppress_print(func):
    """Decorator version of suppress_print context manager.

    :param func: Function to wrap.
    :returns: Wrapped function with suppressed stdout.

    Example::

        >>> @wrap_suppress_print
        ... def noisy():
        ...     print("This won't appear")
        ...     return 42
        >>> noisy()
        42
    """
    @wraps(func)
    def wrapped(*a, **kw):
        with suppress_print():
            return func(*a, **kw)
    return wrapped


if __name__ == '__main__':
    __import__('doctest').testmod()
