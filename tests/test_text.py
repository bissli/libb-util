import math

import pytest

from libb import fix_text, fuzzy_search, is_numeric, parse_number
from libb import random_string, rotate, round_digit_string
from libb import sanitize_vulgar_string, smart_base64, strip_ascii, strtobool
from libb import truncate, uncamel, underscore_to_camelcase


class TestRandomString:
    """Tests for random_string function."""

    def test_random_string_length(self):
        result = random_string(10)
        assert len(result) == 10

    def test_random_string_empty(self):
        result = random_string(0)
        assert result == ''

    def test_random_string_uppercase_and_digits(self):
        result = random_string(100)
        assert all(c.isupper() or c.isdigit() for c in result)


class TestUnderscoreToCamelcase:
    """Tests for underscore_to_camelcase function."""

    def test_underscore_to_camelcase_basic(self):
        assert underscore_to_camelcase('foo_bar_baz') == 'fooBarBaz'

    def test_underscore_to_camelcase_single_word(self):
        assert underscore_to_camelcase('foo') == 'foo'

    def test_underscore_to_camelcase_empty(self):
        assert underscore_to_camelcase('') == ''


class TestUncamel:
    """Tests for uncamel function."""

    def test_uncamel_basic(self):
        assert uncamel('CamelCase') == 'camel_case'

    def test_uncamel_multiple(self):
        assert uncamel('CamelCamelCase') == 'camel_camel_case'

    def test_uncamel_with_numbers(self):
        assert uncamel('Camel2Camel2Case') == 'camel2_camel2_case'

    def test_uncamel_acronym(self):
        assert uncamel('getHTTPResponseCode') == 'get_http_response_code'

    def test_uncamel_leading_acronym(self):
        assert uncamel('HTTPResponseCode') == 'http_response_code'


class TestStripAscii:
    """Tests for strip_ascii function."""

    def test_strip_ascii_removes_unicode(self):
        result = strip_ascii('hello世界')
        assert result == 'hello'

    def test_strip_ascii_preserves_ascii(self):
        result = strip_ascii('hello world')
        assert result == 'hello world'


class TestSanitizeVulgarString:
    """Tests for sanitize_vulgar_string function."""

    def test_sanitize_vulgar_fractions(self):
        result = sanitize_vulgar_string('4¾')
        assert result == '4.75'

    def test_sanitize_mixed_content(self):
        result = sanitize_vulgar_string('Foo: 93¾ - 94⅛')
        assert '93.75' in result
        assert '94.125' in result


class TestRoundDigitString:
    """Tests for round_digit_string function."""

    def test_round_digit_string_with_places(self):
        assert round_digit_string('7283.1234', 3) == '7283.123'

    def test_round_digit_string_no_places(self):
        assert round_digit_string('7283.1234', None) == '7283.1234'

    def test_round_digit_string_integer(self):
        assert round_digit_string('7283', 3) == '7283'

    def test_round_digit_string_strips_whitespace(self):
        assert round_digit_string('  123  ', None) == '123'


class TestParseNumber:
    """Tests for parse_number function."""

    def test_parse_number_with_commas(self):
        assert parse_number('1,200m') == 1200

    def test_parse_number_float(self):
        assert parse_number('100.0') == 100.0

    def test_parse_number_integer(self):
        assert parse_number('100') == 100

    def test_parse_number_small_decimal(self):
        assert parse_number('0.002k') == 0.002

    def test_parse_number_negative(self):
        assert parse_number('-1') == -1

    def test_parse_number_parens_negative(self):
        assert parse_number('(1)') == -1

    def test_parse_number_negative_float(self):
        assert parse_number('-100.0') == -100.0

    def test_parse_number_empty(self):
        assert parse_number('') is None

    def test_parse_number_non_numeric(self):
        assert parse_number('foo') is None

    def test_parse_number_non_numeric_no_force(self):
        assert parse_number('foo', force=False) == 'foo'


class TestTruncate:
    """Tests for truncate function."""

    def test_truncate_basic(self):
        assert truncate('fubarbaz', 6) == 'fub...'

    def test_truncate_no_truncation_needed(self):
        assert truncate('short', 10) == 'short'

    def test_truncate_custom_suffix(self):
        assert truncate('fubarbaz', 3, suffix='..') == 'f..'

    def test_truncate_width_too_small(self):
        with pytest.raises(AssertionError):
            truncate('fubarbaz', 3)


class TestRotate:
    """Tests for rotate function."""

    def test_rotate_basic(self):
        result = rotate('foobarbaz')
        assert result == ';^^-,{-,E'

    def test_rotate_inverse(self):
        # Rotating twice should return to original
        original = 'hello'
        rotated = rotate(original)
        double_rotated = rotate(rotated)
        assert double_rotated == original


class TestStrtobool:
    """Tests for strtobool function."""

    def test_strtobool_true_values(self):
        for val in ['y', 'yes', 't', 'true', 'on', '1', 'YES', 'True']:
            assert strtobool(val) is True

    def test_strtobool_false_values(self):
        for val in ['n', 'no', 'f', 'false', 'off', '0', '']:
            assert strtobool(val) is False

    def test_strtobool_none(self):
        assert strtobool(None) is False

    def test_strtobool_bool_passthrough(self):
        assert strtobool(True) is True
        assert strtobool(False) is False

    def test_strtobool_invalid(self):
        with pytest.raises(ValueError):
            strtobool('maybe')


class TestIsNumeric:
    """Tests for is_numeric function."""

    def test_is_numeric_string_letter(self):
        assert is_numeric('a') is False

    def test_is_numeric_float(self):
        assert is_numeric(1e4) is True

    def test_is_numeric_scientific_string(self):
        assert is_numeric('1E2') is True

    def test_is_numeric_complex(self):
        assert is_numeric(complex(-1, 0)) is False

    def test_is_numeric_integer(self):
        assert is_numeric(42) is True

    def test_is_numeric_negative(self):
        assert is_numeric(-math.pi) is True


class TestFixText:
    """Tests for fix_text function."""

    def test_fix_text_mojibake(self):
        # Test with actual mojibake (UTF-8 incorrectly decoded as Latin-1)
        result = fix_text('caf\xe9')
        assert 'café' in result or result == 'café'

    def test_fix_text_entities(self):
        result = fix_text('Broken text&hellip; it&#x2019;s ﬂubberiﬁc!')
        assert '…' in result
        assert "'" in result

    def test_fix_text_fullwidth(self):
        result = fix_text('ＬＯＵＤ　ＮＯＩＳＥＳ')
        assert result == 'LOUD NOISES'


class TestSmartBase64:
    """Tests for smart_base64 function."""

    def test_smart_base64_basic(self):
        result = smart_base64(
            '=?utf-8?B?U1RaOiBGNFExNSBwcmV2aWV3IOKAkyBUaGUgc3RhcnQgb2YgdGh'
            'lIGNhc2ggcmV0dXJuIHN0b3J5PyBQYXRoIHRvICQyMDAgc3RvY2sgcHJpY2U/?='
        )
        assert 'STZ' in result
        assert '$200 stock price' in result

    def test_smart_base64_plain_text(self):
        result = smart_base64('This is plain text')
        assert result == 'This is plain text'

    def test_smart_base64_multiline(self):
        result = smart_base64(
            '=?UTF-8?B?JDEwTU0rIENJVCBHUk9VUCBUUkFERVMgLSBDSVQgNScyMiAxMDLi'
            'hZ0tMTAz4oWbICBNSw==?=\r\n\t=?UTF-8?B?VA==?='
        )
        assert '$10MM+' in result
        assert 'CIT GROUP' in result

    def test_smart_base64_quoted_printable(self):
        # Lines 309-310 - Q encoding (quoted-printable)
        result = smart_base64('=?UTF-8?Q?Hello_World?=')
        assert 'Hello' in result

    def test_smart_base64_bad_utf8_trailing_c2(self):
        # Line 313 - bad formatting with trailing \xc2 byte
        # SGVsbG/C decodes to b'Hello\xc2'
        result = smart_base64('=?UTF-8?B?SGVsbG/C?=')
        assert 'Hello' in result

    def test_smart_base64_unicode_decode_error(self):
        # Lines 316-318 - UnicodeDecodeError handling with chardet
        # gIGC decodes to b'\x80\x81\x82' which is invalid UTF-8
        result = smart_base64('=?UTF-8?B?gIGC?=')
        # Should not raise, should return something (possibly with replacement chars)
        assert isinstance(result, str)


class TestFuzzySearch:
    """Tests for fuzzy_search function."""

    def test_fuzzy_search_exact_match(self):
        results = list(fuzzy_search('OCR', [('Omnicare', 'OCR'), ('Other', 'XXX')]))
        _, ocr_score = results[0]
        _, other_score = results[1]
        assert ocr_score == 1.0
        assert other_score < ocr_score

    def test_fuzzy_search_partial_match(self):
        results = list(fuzzy_search('Ramco', [('RAMCO-GERSHENSON', 'RPT'), ('Other', 'XXX')]))
        _, ramco_score = results[0]
        assert ramco_score > 0.5

    def test_fuzzy_search_no_match(self):
        results = list(fuzzy_search('XYZ', [('ABC', 'DEF')]))
        _, score = results[0]
        assert score < 1.0

    def test_fuzzy_search_with_non_string_items(self):
        # Line 371 - non-string items are skipped
        results = list(fuzzy_search('test', [('hello', 123, None), ('test', 'TEST')]))
        assert len(results) == 2
        _, score1 = results[0]
        _, score2 = results[1]
        assert score2 == 1.0  # 'TEST' matches 'test' exactly


class TestTruncateEdgeCases:
    """Additional truncate tests for edge cases."""

    def test_truncate_boundary_on_space(self):
        # Line 250 - truncate where w (width - len(suffix)) lands on a space
        # For 'hello world': h=0 e=1 l=2 l=3 o=4 space=5 w=6 o=7 r=8 l=9 d=10
        # width=8, suffix='...', w=8-3=5, s[5] is space
        result = truncate('hello world test', 8)
        assert result == 'hello...'

    def test_truncate_with_words(self):
        result = truncate('hello wonderful world', 15)
        assert '...' in result


class TestParseNumberEdgeCases:
    """Additional parse_number tests."""

    def test_parse_number_trailing_dot(self):
        assert parse_number('100.') == 100.0

    def test_parse_number_parens_trailing_dot(self):
        assert parse_number('(100.)') == -100.0

    def test_parse_number_only_letters_no_force(self):
        # When no numbers found and force=False, return original
        result = parse_number('abc', force=False)
        assert result == 'abc'

    def test_parse_number_invalid_numeric_no_force(self):
        # Line 225 - num exists but can't be converted to int/float
        # "((" has parens so num is "((" but can't convert
        result = parse_number('((', force=False)
        assert result == '(('


class TestSanitizeVulgarStringEdgeCases:
    """Additional sanitize_vulgar_string tests."""

    def test_sanitize_standalone_fraction(self):
        result = sanitize_vulgar_string('⅛')
        assert '0.125' in result


class TestRoundDigitStringEdgeCases:
    """Additional round_digit_string tests."""

    def test_round_digit_string_non_numeric(self):
        # When value isn't numeric, return as-is
        result = round_digit_string('not a number')
        assert result == 'not a number'


if __name__ == '__main__':
    pytest.main([__file__])
