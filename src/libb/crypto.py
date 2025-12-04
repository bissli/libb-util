"""Cryptography and encoding utilities."""

import base64
import logging
import pathlib

logger = logging.getLogger(__name__)

__all__ = [
    'base64file',
    'kryptophy',
]


def base64file(fil):
    """Encode file contents as base64.

    :param fil: Path to file to encode.
    :returns: Base64 encoded bytes.
    :rtype: bytes

    Example::

        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        ...     _ = f.write('hello world')
        >>> base64file(f.name)
        b'aGVsbG8gd29ybGQ=\\n'

    .. note::
        This function reads the entire file into memory.
        Use with caution on large files.
    """
    return base64.encodebytes(pathlib.Path(fil).read_bytes())


def kryptophy(blah):
    """Converts a string to an integer by concatenating hex values of characters.

    :param str blah: String to convert.
    :returns: Integer representation of the string.
    :rtype: int

    Example::

        >>> kryptophy('AB')
        16706
        >>> kryptophy('hello')
        448378203247
    """
    return int('0x' + ''.join([hex(ord(x))[2:] for x in blah]), 16)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
