import csv
import io
import json
import logging
from collections.abc import Iterable
from functools import wraps
from zipfile import ZipFile, ZipInfo

logger = logging.getLogger(__name__)


def render_csv(rows, dialect=csv.excel):
    """Quick helper routine to output a csv string."""
    f = io.StringIO()
    writer = csv.writer(f, dialect=dialect)
    for row in rows:
        writer.writerow(row)
    return f.getvalue()


class CsvZip(ZipFile):
    """Zipped csv file that handles file permissions correctly on dos
    re: http://stackoverflow.com/q/279945/424380
    """

    @property
    def value(self):
        self.close()
        return self.__buffer.getvalue()

    def __init__(self):
        self.__buffer = io.StringIO()
        ZipFile.__init__(self, self.__buffer, 'w')

    def writecsv(self, filename, data):
        info = ZipInfo(f'{filename}.csv')
        info.external_attr = 0o644 << 16
        self.writestr(info, render_csv(data))


def iterable_to_stream(iterable, buffer_size=io.DEFAULT_BUFFER_SIZE):
    """Iterable that yields bytestrings as a read-only input stream
    re: https://stackoverflow.com/a/20260030
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
    """General wrapper that converts input param to a stream"""

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
    """Parse ascii encoded json from ascii encoded file"""
    return _byteify(json.load(file_handle, object_hook=_byteify), ignore_dicts=True)


def json_loads_byteified(json_text):
    """Parse ascii encoded json from ascii encoded text

    >>> json_loads_byteified('{"foo": "bar"}')
    {'foo': 'bar'}
    >>> json_loads_byteified('{"foo": "bar", "things": [7, {"qux": "baz", "moo": {"cow": ["milk"]}}]}')
    {'foo': 'bar', 'things': [7, {'qux': 'baz', 'moo': {'cow': ['milk']}}]}
    """
    return _byteify(json.loads(json_text, object_hook=_byteify), ignore_dicts=True)


def _byteify(data, ignore_dicts=False):
    """Load string from Json"""
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True) for key, value in list(data.items())
        }
    return data


if __name__ == '__main__':
    __import__('doctest').testmod()
