"""Cryptography and encoding utilities"""

import base64
import logging
import pathlib

logger = logging.getLogger(__name__)

__all__ = [
    'base64file',
    'kryptophy',
]


def base64file(fil):
    """Encode file contents as base64

    Note: This function reads the entire file into memory.
    Use with caution on large files.
    """
    return base64.encodebytes(pathlib.Path(fil).read_bytes())


def kryptophy(blah):
    """Intentionally mysterious

    Converts a string to an integer by concatenating hex values of characters.
    """
    return int('0x' + ''.join([hex(ord(x))[2:] for x in blah]), 16)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
