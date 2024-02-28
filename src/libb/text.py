import base64
import contextlib
import logging
import quopri
import random
import re
import string
import unicodedata
from functools import reduce

from libb.util import collapse

with contextlib.suppress(ImportError):
    import chardet

with contextlib.suppress(ImportError):
    import ftfy

with contextlib.suppress(ImportError):
    from rapidfuzz.distance import JaroWinkler
    from rapidfuzz.fuzz import token_set_ratio
    from rapidfuzz.process import extract

logger = logging.getLogger(__name__)

#
# useful constants for writing unicode-based context-free grammars
#

UNI_ALL = ''.join(chr(_) for _ in range(65536))
UNI_DECIMALS = ''.join(_ for _ in UNI_ALL if unicodedata.category(_) == 'Nd')
UNI_SLASHES = chr(47) + chr(8260) + chr(8725)
UNI_SUPERSCRIPTS = chr(8304) + chr(185) + chr(178) + chr(179) + ''.join(chr(_) for _ in range(8308, 8314))
UNI_SUBSCRIPTS = ''.join(chr(_) for _ in range(8320, 8330))
UNI_VULGAR_FRACTIONS = chr(188) + chr(189) + chr(190) + ''.join(chr(_) for _ in range(8531, 8543))

SUPERSCRIPT = dict(list(zip(UNI_SUPERSCRIPTS, list(range(10)))))
SUBSCRIPT = dict(list(zip(UNI_SUBSCRIPTS, list(range(10)))))

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
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(length))


def fix_text(text):
    r"""Uses ftfy magic to fix text issues

    >>> fix_text('âœ” No problems')
    '✔ No problems'
    >>> print(fix_text("&macr;\\_(ã\x83\x84)_/&macr;"))
    ¯\_(ツ)_/¯
    >>> fix_text('Broken text&hellip; it&#x2019;s ﬂubberiﬁc!')
    "Broken text… it's flubberific!"
    >>> fix_text('ＬＯＵＤ　ＮＯＩＳＥＳ')
    'LOUD NOISES'
    """
    return ftfy.fix_text(text)


def underscore_to_camelcase(s):
    """Converts underscore_delimited_text to camelCase

    >>> underscore_to_camelcase('foo_bar_baz')
    'fooBarBaz'
    """
    return ''.join(word.title() if i else word.lower() for i, word in enumerate(s.split('_')))


def uncamel(camel):
    """Uncamel something in camel case, for christ's sake!!
    http://stackoverflow.com/a/1176023

    >>> uncamel('CamelCase')
    'camel_case'
    >>> uncamel('CamelCamelCase')
    'camel_camel_case'
    >>> uncamel('Camel2Camel2Case')
    'camel2_camel2_case'
    >>> uncamel('getHTTPResponseCode')
    'get_http_response_code'
    >>> uncamel('get2HTTPResponseCode')
    'get2_http_response_code'
    >>> uncamel('HTTPResponseCode')
    'http_response_code'
    >>> uncamel('HTTPResponseCodeXYZ')
    'http_response_code_xyz'
    """
    uncased = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', camel)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', uncased).lower()


def sanitize_vulgar_string(s):
    """Replaces number and vulgar fractions combos with number and decimal

    >>> sanitize_vulgar_string("Foo-Bar+Baz: 17s 4¾ 1 ⅛ 20 93¾ - 94⅛")
    'Foo-Bar+Baz: 17s 4.75 1.125 20 93.75 - 94.125'
    """
    sanitize = re.compile(rf"(\d*)\s*({'|'.join(VULGAR_FRACTION)})")

    def _sum(val, el, lookup=VULGAR_FRACTION.get):
        if frac := lookup(el):
            return str(float(val) + frac) if val else ' ' + str(frac)
        return str(float(val) + float(el))

    for f in sanitize.finditer(s):
        m, it = f.group(), f.groups()
        s = s.replace(m, reduce(_sum, it))

    return s


def round_digit_string(s, places=3) -> str:
    """Clean string comprised of digits

    >>> round_digit_string('7283.1234')
    '7283.123'
    >>> round_digit_string('7283')
    '7283'

    """
    s = s.strip()
    with contextlib.suppress(ValueError):
        f = float(s)
        i = int(f)
        s = i if f == i else round(f, places)
        return str(s)
    return s


def truncate(s, width, suffix='...'):
    """Truncate a string to max width chars
    Add the suffix if the string was truncated

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
    """Apply rot13-like translation to string, including digits and punctuation

    >>> rotate("foobarbaz")
    ';^^-,{-,E'
    """
    instr = string.ascii_lowercase + string.digits + string.punctuation + string.ascii_uppercase
    midpoint = len(instr) // 2
    outstr = instr[midpoint:] + instr[:midpoint]
    return str.translate(s, str.maketrans(instr, outstr))


def smart_base64(encoded_words):
    r"""Additional intelligent defaults for en/decoding base 64

    what we need to do in real life:

    #. split out encoded words per
       [RFC 2047, Section 2](http://tools.ietf.org/html/rfc2047#section-2)

    >>> smart_base64('=?utf-8?B?U1RaOiBGNFExNSBwcmV2aWV3IOKAkyBUaGUgc3RhcnQgb2YgdGh'
    ...              'lIGNhc2ggcmV0dXJuIHN0b3J5PyBQYXRoIHRvICQyMDAgc3RvY2sgcHJpY2U/?=')
    'STZ: F4Q15 preview – The start of the cash return story? Path to $200 stock price?'

    common bug in email subjects is that multiline subjects are base64 encoded
    *per line* so we get non-base64 characters:
    >>> smart_base64('=?UTF-8?B?JDEwTU0rIENJVCBHUk9VUCBUUkFERVMgLSBDSVQgNScyMiAxMDLi'
    ...              'hZ0tMTAz4oWbICBNSw==?=\r\n\t=?UTF-8?B?VA==?=')
    "$10MM+ CIT GROUP TRADES - CIT 5'22 102.625-103.125 MK T"

    this one specifies UTF-8 but it is actually encoding Latin-1 characters for
    the 3/4's, 1/8's, 3/4's, 1/8's, 1/2's:
    >>> smart_base64('=?UTF-8?B?TVMgZW5lcmd5OiByaWcgMTdzIDkxwr4vOTLihZsgMThzIDkzwr4v'
    ...              'OTTihZsgMjBzIDgywg==?=\r\n\t=?UTF-8?B?vS84Mw==?=')
    'MS energy: rig 17s 91.75/92.125 18s 93.75/94.125 20s 82.5/83'

    >>> smart_base64('=?UTF-8?B?VGhpcyBpcyBhIGhvcnNleTog8J+Qjg==?=')
    'This is a horsey: \U0001f40e'

    >>> smart_base64('=?UTF-8?B?U0xBQiAxIOKFnDogIDEwOSAtIMK9IHYgNzYuMjU=?=')
    'SLAB 1.375: 109 - 0.5 v 76.25'
    """
    re_encoded = r'=\?{1}(.+)\?{1}([B|Q])\?{1}(.+)\?{1}='

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
    """Convert a string representation of truth to true (1) or false (0).
    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    if val is None:
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        val = val.lower()
        if val in {'y', 'yes', 't', 'true', 'on', '1'}:
            return True
        elif val in {'', 'n', 'no', 'f', 'false', 'off', '0'}:
            return False
    raise ValueError('invalid truth value %r' % (val,))


def fuzzy_search(search_term, items, case_sensitive=False):
    """Search for term in a list of items with one or more terms
    Scores each lower-cased "word" (split by space, -, and _) separately
    Returns the highest score **very** brute force, FIXME improve it

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


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
