import base64
import contextlib
import logging
import quopri
import random
import string
import unicodedata

import regex as re

from libb._libb import collapse, sanitize_vulgar_string, uncamel
from libb._libb import underscore_to_camelcase

with contextlib.suppress(ImportError):
    import chardet

with contextlib.suppress(ImportError):
    import ftfy

logger = logging.getLogger(__name__)

__all__ = [
    'random_string',
    'fix_text',
    'underscore_to_camelcase',
    'uncamel',
    'strip_ascii',
    'sanitize_vulgar_string',
    'round_digit_string',
    'parse_number',
    'truncate',
    'rotate',
    'smart_base64',
    'strtobool',
    'fuzzy_search',
    'is_numeric',
]

#
# useful constants for writing unicode-based context-free grammars
#

# Unicode constants for context-free grammars
UNI_ALL = ''.join(chr(_) for _ in range(65536))
UNI_DECIMALS = ''.join(_ for _ in UNI_ALL if unicodedata.category(_) == 'Nd')
UNI_SLASHES = chr(47) + chr(8260) + chr(8725)
UNI_SUPERSCRIPTS = chr(8304) + chr(185) + chr(178) + chr(179) + ''.join(chr(_) for _ in range(8308, 8314))
UNI_SUBSCRIPTS = ''.join(chr(_) for _ in range(8320, 8330))
UNI_VULGAR_FRACTIONS = chr(188) + chr(189) + chr(190) + ''.join(chr(_) for _ in range(8531, 8543))

SUPERSCRIPT = dict(list(zip(UNI_SUPERSCRIPTS, list(range(10)))))
SUBSCRIPT = dict(list(zip(UNI_SUBSCRIPTS, list(range(10)))))

# Vulgar fraction mapping kept for backwards compatibility
_VULGAR_FRACTIONS = (
    1 / 4.0,
    2 / 4.0,
    3 / 4.0,
    1 / 3.0,
    2 / 3.0,
    1 / 5.0,
    2 / 5.0,
    3 / 5.0,
    4 / 5.0,
    1 / 6.0,
    5 / 6.0,
    1 / 8.0,
    3 / 8.0,
    5 / 8.0,
    7 / 8.0,
)
VULGAR_FRACTION = dict(list(zip(UNI_VULGAR_FRACTIONS, _VULGAR_FRACTIONS)))


def random_string(length):
    """Generate a random alphanumeric string.

    :param int length: Length of the string to generate.
    :returns: Random string of uppercase letters and digits.
    :rtype: str
    """
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(length))


def fix_text(text):
    r"""Use ftfy magic to fix text encoding issues.

    :param str text: Text to fix.
    :returns: Fixed text.
    :rtype: str

    Example::

        >>> fix_text('âœ" No problems')  # doctest: +SKIP
        '✔ No problems'
        >>> print(fix_text("&macr;\\_(ã\x83\x84)_/&macr;"))
        ¯\_(ツ)_/¯
        >>> fix_text('Broken text&hellip; it&#x2019;s ﬂubberiﬁc!')
        "Broken text… it's flubberific!"
        >>> fix_text('ＬＯＵＤ　ＮＯＩＳＥＳ')
        'LOUD NOISES'
    """
    return ftfy.fix_text(text)


# underscore_to_camelcase and uncamel are now implemented in Rust
# See libb._libb for the implementations


def strip_ascii(s):
    """Remove non-ASCII characters from a string.

    :param str s: Input string.
    :returns: String with only ASCII characters.
    :rtype: str
    """
    return s.encode('ascii', errors='ignore').decode()


# sanitize_vulgar_string is now implemented in Rust
# See libb._libb for the implementation


def round_digit_string(s, places=None) -> str:
    """Round a numeric string to specified decimal places.

    :param str s: Numeric string to round.
    :param int places: Number of decimal places (None to preserve original).
    :returns: Rounded numeric string.
    :rtype: str

    Example::

        >>> round_digit_string('7283.1234', 3)
        '7283.123'
        >>> round_digit_string('7283.1234', None)
        '7283.1234'
        >>> round_digit_string('7283', 3)
        '7283'
    """
    s = s.strip()
    with contextlib.suppress(ValueError):
        f = float(s)
        i = int(f)
        if f == i:
            s = i
        elif places:
            s = round(f, places)
        else:
            s = f
        return str(s)
    return s


def parse_number(s: str, force=True):
    """Extract number from string.

    Handles various formats including commas, parentheses for negatives,
    and trailing characters.

    :param str s: String to parse.
    :param bool force: If True, return None on parse failure; if False, return original string.
    :returns: Parsed int or float, None, or original string (if force=False).

    Example::

        >>> parse_number('1,200m')
        1200
        >>> parse_number('100.0')
        100.0
        >>> parse_number('100')
        100
        >>> parse_number('0.002k')
        0.002
        >>> parse_number('-1')
        -1
        >>> parse_number('(1)')
        -1
        >>> parse_number('-100.0')
        -100.0
        >>> parse_number('(100.)')
        -100.0
        >>> parse_number('')
        >>> parse_number('foo')
        >>> parse_number('foo', force=False)
        'foo'
    """
    if not s:
        return
    if s.endswith('.'):
        s+='0'
    if s.endswith('.)'):
        s = s[:-2]+'.0)'
    num = ''.join(re.findall(r'[\(-\d\.\)]+', s))
    if not num and force:
        return
    if not num:
        return s
    if neg := re.match(r'^\((.*)\)$', num):
        num = '-'+neg.group(1)
    i = f = None
    with contextlib.suppress(Exception):
        i = int(num)
    with contextlib.suppress(Exception):
        f = float(num)
    if not force and (i is None and f is None):
        return s
    if i == f:
        return i
    return f


def truncate(s, width, suffix='...'):
    """Truncate a string to max width characters.

    Adds suffix if the string was truncated. Tries to break on whitespace.

    :param str s: String to truncate.
    :param int width: Maximum width including suffix.
    :param str suffix: Suffix to append when truncated.
    :returns: Truncated string.
    :rtype: str
    :raises AssertionError: If width is not longer than suffix.

    Example::

        >>> truncate('fubarbaz', 6)
        'fub...'
        >>> truncate('fubarbaz', 3)
        Traceback (most recent call last):
            ...
        AssertionError: Desired width must be longer than suffix
        >>> truncate('fubarbaz', 3, suffix='..')
        'f..'
    """
    assert width > len(suffix), 'Desired width must be longer than suffix'
    if len(s) <= width:
        return s
    w = width - len(suffix)
    # if the boundary is on a space, don't include it
    if s[w].isspace():
        return s[:w] + suffix
    # break on the first whitespace from the end
    return s[:w].rsplit(None, 1)[0] + suffix


def rotate(s):
    """Apply rot13-like translation to string.

    Rotates characters including digits and punctuation.

    :param str s: String to rotate.
    :returns: Rotated string.
    :rtype: str

    Example::

        >>> rotate("foobarbaz")
        ';^^-,{-,E'
    """
    instr = string.ascii_lowercase + string.digits + string.punctuation + string.ascii_uppercase
    midpoint = len(instr) // 2
    outstr = instr[midpoint:] + instr[:midpoint]
    return str.translate(s, str.maketrans(instr, outstr))


def smart_base64(encoded_words):
    r"""Decode base64 encoded words with intelligent charset handling.

    Splits out encoded words per RFC 2047, Section 2 and handles common
    encoding issues like multiline subjects and charset mismatches.

    :param str encoded_words: Base64 encoded string or plain text.
    :returns: Decoded string (or original if not encoded).
    :rtype: str

    .. note::
        See `RFC 2047, Section 2 <http://tools.ietf.org/html/rfc2047#section-2>`_

    Basic Usage::

        >>> smart_base64('=?utf-8?B?U1RaOiBGNFExNSBwcmV2aWV3IOKAkyBUaGUgc3RhcnQgb2YgdGh'
        ...              'lIGNhc2ggcmV0dXJuIHN0b3J5PyBQYXRoIHRvICQyMDAgc3RvY2sgcHJpY2U/?=')
        'STZ: F4Q15 preview – The start of the cash return story? Path to $200 stock price?'

    Multiline Subjects (common email bug - base64 encoded per line)::

        >>> smart_base64('=?UTF-8?B?JDEwTU0rIENJVCBHUk9VUCBUUkFERVMgLSBDSVQgNScyMiAxMDLi'
        ...              'hZ0tMTAz4oWbICBNSw==?=\r\n\t=?UTF-8?B?VA==?=')
        "$10MM+ CIT GROUP TRADES - CIT 5'22 102.625-103.125 MK T"

    Charset Mismatch (UTF-8 header with Latin-1 content)::

        >>> smart_base64('=?UTF-8?B?TVMgZW5lcmd5OiByaWcgMTdzIDkxwr4vOTLihZsgMThzIDkzwr4v'
        ...              'OTTihZsgMjBzIDgywg==?=\r\n\t=?UTF-8?B?vS84Mw==?=')
        'MS energy: rig 17s 91.75/92.125 18s 93.75/94.125 20s 82.5/83'

    Unicode Characters::

        >>> smart_base64('=?UTF-8?B?VGhpcyBpcyBhIGhvcnNleTog8J+Qjg==?=')
        'This is a horsey: \U0001f40e'
        >>> smart_base64('=?UTF-8?B?U0xBQiAxIOKFnDogIDEwOSAtIMK9IHYgNzYuMjU=?=')
        'SLAB 1.375: 109 - 0.5 v 76.25'

    Plain Text Passthrough::

        >>> smart_base64('This is plain text')
        'This is plain text'
    """
    re_encoded = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='

    if not re.search(re_encoded, encoded_words):
        return encoded_words

    def decode(charset, encoding, encoded_text):
        if encoding == 'B':
            fn = base64.urlsafe_b64decode if '-' in encoded_text or '\\' in encoded_text else base64.standard_b64decode
            byte_string = fn(encoded_text)
        elif encoding == 'Q':
            byte_string = quopri.decodestring(encoded_text)
        for chunk in byte_string.split():
            if m := re.match(rb'(.*)\xc2$', chunk):
                chunk = m.groups()[0]  # bad formatting
            try:
                yield chunk.decode(charset, 'strict')
            except UnicodeDecodeError:
                enc = chardet.detect(chunk)['encoding']
                yield chunk.decode(enc or charset, 'replace')

    decoded = []
    for c, e, t in re.findall(re_encoded, encoded_words):
        expand = list(collapse(list(decode(c, e, t))))
        decoded.extend(expand)

    return sanitize_vulgar_string(' '.join(decoded))


def strtobool(val):
    """Convert a string representation of truth to boolean.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'.
    False values are 'n', 'no', 'f', 'false', 'off', '0', and empty string.

    :param val: Value to convert (string, bool, or None).
    :returns: Boolean value.
    :rtype: bool
    :raises ValueError: If val is not a recognized truth value.
    """
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val = val.lower()
        if val in {'y', 'yes', 't', 'true', 'on', '1'}:
            return True
        if val in {'', 'n', 'no', 'f', 'false', 'off', '0'}:
            return False
    raise ValueError(f'invalid truth value {val!r}')


def fuzzy_search(search_term, items, case_sensitive=False):
    """Search for term in a list of items using fuzzy matching.

    Scores each item using Jaro-Winkler similarity and token set ratio,
    returning the highest score for each item tuple.

    :param str search_term: Term to search for.
    :param items: Iterable of tuples containing searchable strings.
    :param bool case_sensitive: Whether to use case-sensitive matching.
    :yields: Tuples of (items, max_score).

    Example::

        >>> results = fuzzy_search("OCR", [("Omnicare", "OCR",), ("Ocra", "OKK"), ("GGG",)])
        >>> (_,ocr_score), (_,okk_score), (_,ggg_score) = results
        >>> '{:.4}'.format(ocr_score)
        '1.0'
        >>> '{:.4}'.format(okk_score)
        '0.9417'
        >>> '{:.4}'.format(ggg_score)
        '0.0'
        >>> x, y = list(zip(*fuzzy_search("Ramco-Gers",
        ...     [("RAMCO-GERSHENSON PROPERTIES", "RPT US Equity",),
        ...     ("Ramco Inc.", "RMM123FAKE")])))[1]
        >>> '{:.4}'.format(x), '{:.4}'.format(y)
        ('0.8741', '0.6667')
    """
    from rapidfuzz.distance import JaroWinkler
    from rapidfuzz.fuzz import token_set_ratio
    from rapidfuzz.process import extract

    _search_term = search_term.lower() if not case_sensitive else search_term
    for _items in items:
        max_score = 0.0
        for item in _items:
            if not isinstance(item, str):
                continue
            _item = item.lower() if not case_sensitive else item
            _jaro = JaroWinkler.similarity(_search_term, _item)
            _fuzz = extract(_search_term, [_item], scorer=token_set_ratio)[
                -1
            ][-1]
            max_score = float(max(max_score, _jaro, _fuzz / 100.0))
        yield _items, max_score


def is_numeric(txt):
    """Check if value can be converted to a float.

    :param txt: Value to check.
    :returns: True if value can be converted to float.
    :rtype: bool

    .. warning::
        Complex types cannot be converted to float.

    Example::

        >>> is_numeric('a')
        False
        >>> is_numeric(1e4)
        True
        >>> is_numeric('1E2')
        True
        >>> is_numeric(complex(-1,0))
        False
    """
    try:
        float(txt)
        return True
    except (ValueError, TypeError):
        return False


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
