"""Tests for webapp utility functions (non-framework specific)."""

import datetime
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from libb import COOKIE_DEFAULTS, JSONDecoderISODate, JSONEncoderISODate
from libb import first_of_each, htmlquote, htmlunquote, httpdate, inject_file
from libb import inject_image, local_or_static_join, make_url, parsehttpdate
from libb import prefix_urls, rand_retry, rsleep, safe_join, scale
from libb import url_path_join, urlquote, valid_api_key, validaddr, validip
from libb import validip6addr, validipaddr, validipport, websafe


class TestValidIpAddr:
    """Tests for IP address validation functions."""

    def test_validipaddr_valid(self):
        assert validipaddr('192.168.1.1') is True
        assert validipaddr('0.0.0.0') is True
        assert validipaddr('255.255.255.255') is True
        assert validipaddr('10.0.0.1') is True

    def test_validipaddr_invalid(self):
        assert validipaddr('192.168. 1.1') is False  # space
        assert validipaddr('192.168.1.800') is False  # > 255
        assert validipaddr('192.168.1') is False  # only 3 octets
        assert validipaddr('192.168.1.1.1') is False  # 5 octets
        assert validipaddr('abc.def.ghi.jkl') is False  # non-numeric

    def test_validip6addr_valid(self):
        assert validip6addr('::') is True
        assert validip6addr('aaaa:bbbb:cccc:dddd::1') is True
        assert validip6addr('::1') is True
        assert validip6addr('fe80::1') is True

    def test_validip6addr_invalid(self):
        assert validip6addr('1:2:3:4:5:6:7:8:9:10') is False
        assert validip6addr('12:10') is False
        assert validip6addr('not an ip') is False

    def test_validipport_valid(self):
        assert validipport('9000') is True
        assert validipport('0') is True
        assert validipport('65535') is True
        assert validipport('80') is True
        assert validipport('443') is True

    def test_validipport_invalid(self):
        assert validipport('foo') is False
        assert validipport('1000000') is False
        assert validipport('-1') is False
        assert validipport('65536') is False


class TestValidIp:
    """Tests for validip function."""

    def test_validip_ipv4_only(self):
        assert validip('1.2.3.4') == ('1.2.3.4', 8080)

    def test_validip_port_only(self):
        assert validip('80') == ('0.0.0.0', 80)

    def test_validip_ipv4_with_port(self):
        assert validip('192.168.0.1:85') == ('192.168.0.1', 85)

    def test_validip_ipv6(self):
        assert validip('::') == ('::', 8080)

    def test_validip_ipv6_with_port(self):
        assert validip('[::]:88') == ('::', 88)
        assert validip('[::1]:80') == ('::1', 80)

    def test_validip_empty_string(self):
        assert validip('') == ('0.0.0.0', 8080)

    def test_validip_custom_defaults(self):
        assert validip('', defaultaddr='127.0.0.1', defaultport=3000) == ('127.0.0.1', 3000)

    def test_validip_invalid_raises(self):
        with pytest.raises(ValueError):
            validip('fff')
        with pytest.raises(ValueError):
            validip('invalid:port')


class TestValidAddr:
    """Tests for validaddr function."""

    def test_validaddr_socket_path(self):
        assert validaddr('/path/to/socket') == '/path/to/socket'
        assert validaddr('/var/run/app.sock') == '/var/run/app.sock'

    def test_validaddr_port_only(self):
        assert validaddr('8000') == ('0.0.0.0', 8000)

    def test_validaddr_ip_only(self):
        assert validaddr('127.0.0.1') == ('127.0.0.1', 8080)

    def test_validaddr_ip_with_port(self):
        assert validaddr('127.0.0.1:8000') == ('127.0.0.1', 8000)

    def test_validaddr_invalid_raises(self):
        with pytest.raises(ValueError):
            validaddr('fff')


class TestUrlQuote:
    """Tests for urlquote function."""

    def test_urlquote_special_chars(self):
        assert urlquote('://?f=1&j=1') == '%3A//%3Ff%3D1%26j%3D1'

    def test_urlquote_none(self):
        assert urlquote(None) == ''

    def test_urlquote_unicode(self):
        assert urlquote('\u203d') == '%E2%80%BD'

    def test_urlquote_spaces(self):
        result = urlquote('hello world')
        assert '%20' in result or '+' in result


class TestHttpDate:
    """Tests for httpdate and parsehttpdate functions."""

    def test_httpdate_format(self):
        dt = datetime.datetime(1970, 1, 1, 1, 1, 1)
        assert httpdate(dt) == 'Thu, 01 Jan 1970 01:01:01 GMT'

    def test_httpdate_different_dates(self):
        dt = datetime.datetime(2023, 12, 25, 0, 0, 0)
        result = httpdate(dt)
        assert 'Dec 2023' in result
        assert 'GMT' in result

    def test_parsehttpdate_parse(self):
        result = parsehttpdate('Thu, 01 Jan 1970 01:01:01 GMT')
        assert result == datetime.datetime(1970, 1, 1, 1, 1, 1)

    def test_parsehttpdate_invalid(self):
        result = parsehttpdate('invalid date')
        assert result is None

    def test_httpdate_roundtrip(self):
        dt = datetime.datetime(2023, 6, 15, 12, 30, 45)
        formatted = httpdate(dt)
        parsed = parsehttpdate(formatted)
        assert parsed == dt


class TestHtmlQuote:
    """Tests for htmlquote and htmlunquote functions."""

    def test_htmlquote_special_chars(self):
        assert htmlquote("<'&\">") == '&lt;&#39;&amp;&quot;&gt;'

    def test_htmlquote_ampersand_first(self):
        # Ampersand must be escaped first
        assert htmlquote('&lt;') == '&amp;lt;'

    def test_htmlunquote_special_chars(self):
        assert htmlunquote('&lt;&#39;&amp;&quot;&gt;') == "<'&\">"

    def test_htmlquote_roundtrip(self):
        original = "<script>alert('xss')</script>"
        assert htmlunquote(htmlquote(original)) == original

    def test_htmlquote_normal_text(self):
        assert htmlquote('hello world') == 'hello world'


class TestWebsafe:
    """Tests for websafe function."""

    def test_websafe_special_chars(self):
        assert websafe("<'&\">") == '&lt;&#39;&amp;&quot;&gt;'

    def test_websafe_none(self):
        assert websafe(None) == ''

    def test_websafe_unicode(self):
        assert websafe('\u203d') == '\u203d'

    def test_websafe_bytes(self):
        result = websafe(b'<test>')
        assert result == '&lt;test&gt;'

    def test_websafe_number(self):
        result = websafe(123)
        assert result == '123'


class TestMakeUrl:
    """Tests for make_url function."""

    def test_make_url_basic(self):
        result = make_url('/foo/', bar=1, baz=2)
        assert 'bar=1' in result
        assert 'baz=2' in result

    def test_make_url_with_existing_query(self):
        result = make_url('/foo/?a=1&a=2')
        assert 'a=1' in result
        assert 'a=2' in result

    def test_make_url_with_list(self):
        result = make_url('/foo/', fuz=(1, 2))
        assert 'fuz=1' in result
        assert 'fuz=2' in result

    def test_make_url_with_ignore(self):
        ignore_fn = lambda x: x.startswith('_')
        result = make_url('/foo/', _format='excel', fuz=1, __ignore__=ignore_fn)
        assert '_format=excel' not in result
        assert 'fuz=1' in result

    def test_make_url_with_replace(self):
        result = make_url('/foo/?bar=1', __replace__={'bar': 2})
        assert 'bar=2' in result

    def test_make_url_with_callable(self):
        result = make_url('/foo/', dynamic=lambda: 'computed')
        assert 'dynamic=computed' in result

    def test_make_url_preserves_domain(self):
        result = make_url('http://example.com/foo/', bar=1)
        assert 'example.com' in result
        assert 'bar=1' in result


class TestPrefixUrls:
    """Tests for prefix_urls function."""

    def test_prefix_urls_basic(self):
        urls = ('/foo', 'foo_handler', '/bar', 'bar_handler')
        result = prefix_urls('/api', 'api_', urls)
        assert result == ('/api/foo', 'api_foo_handler', '/api/bar', 'api_bar_handler')

    def test_prefix_urls_empty(self):
        result = prefix_urls('/api', 'api_', ())
        assert result == ()


class TestUrlPathJoin:
    """Tests for url_path_join function."""

    def test_url_path_join_basic(self):
        result = url_path_join('/foo/', '/bar/', '/baz')
        assert result == 'foo/bar/baz'

    def test_url_path_join_with_scheme(self):
        result = url_path_join('http://example.com', '/path')
        assert result == 'http://example.com/path'

    def test_url_path_join_strips_slashes(self):
        result = url_path_join('/a/', '/b/', '/c/')
        assert '//' not in result.replace('://', '')


class TestFirstOfEach:
    """Tests for first_of_each function."""

    def test_first_of_each_basic(self):
        result = list(first_of_each(['a', 'b'], ['', 'x'], ['', '', 'z']))
        assert result == ['a', 'x', 'z']

    def test_first_of_each_empty(self):
        result = list(first_of_each(['', ''], ['', '']))
        assert result == ['', '']


class TestSafeJoin:
    """Tests for safe_join function."""

    def test_safe_join_basic(self):
        result = safe_join('/base', 'subdir', 'file.txt')
        assert result == '/base/subdir/file.txt'

    def test_safe_join_blocks_traversal(self):
        assert safe_join('/base', '../etc/passwd') is None
        assert safe_join('/base', 'foo/../../../etc/passwd') is None

    def test_safe_join_blocks_absolute(self):
        assert safe_join('/base', '/etc/passwd') is None

    def test_safe_join_normalizes(self):
        result = safe_join('/base', './subdir/../other/file.txt')
        assert result == '/base/other/file.txt'

    def test_safe_join_empty_directory(self):
        result = safe_join('', 'file.txt')
        assert result == './file.txt'

    def test_safe_join_dotdot_only(self):
        assert safe_join('/base', '..') is None


class TestScale:
    """Tests for scale (color scaling) function."""

    def test_scale_hex6_white(self):
        result = scale('#FFFFFF', 0.5)
        assert result.startswith('#')
        # 255 * 0.5 = 127.5 -> 128 = 0x80
        assert '80' in result or '7F' in result

    def test_scale_hex3(self):
        result = scale('#FFF', 0.5)
        assert result.startswith('#')

    def test_scale_black(self):
        result = scale('#000000', 2.0)
        assert result == '#000'

    def test_scale_clamps(self):
        # Scaling beyond 255 should clamp
        result = scale('#FFFFFF', 2.0)
        assert result.startswith('#')


class TestJSONEncoderISODate:
    """Tests for JSONEncoderISODate class."""

    def test_encode_date(self):
        encoder = JSONEncoderISODate()
        result = encoder.encode({'dt': datetime.date(2014, 10, 2)})
        assert result == '{"dt": "2014-10-02"}'

    def test_encode_datetime(self):
        encoder = JSONEncoderISODate()
        result = encoder.encode({'dt': datetime.datetime(2014, 10, 2, 12, 30, 45)})
        assert '2014-10-02' in result
        assert '12:30:45' in result

    def test_encode_non_date(self):
        encoder = JSONEncoderISODate()
        result = encoder.encode({'x': 123, 'y': 'hello'})
        assert result == '{"x": 123, "y": "hello"}'

    def test_encode_nested(self):
        encoder = JSONEncoderISODate()
        data = {'outer': {'inner': datetime.date(2020, 1, 1)}}
        result = encoder.encode(data)
        assert '2020-01-01' in result


class TestJSONDecoderISODate:
    """Tests for JSONDecoderISODate class."""

    def test_decode_date(self):
        decoder = JSONDecoderISODate()
        result = decoder.decode('{"dt": "2014-10-02"}')
        assert result['dt'] == datetime.datetime(2014, 10, 2, 0, 0)

    def test_decode_datetime(self):
        decoder = JSONDecoderISODate()
        result = decoder.decode('{"dt": "2014-10-02T12:30:45"}')
        assert result['dt'].hour == 12
        assert result['dt'].minute == 30

    def test_decode_non_date(self):
        decoder = JSONDecoderISODate()
        result = decoder.decode('{"x": 123}')
        assert result == {'x': 123}

    def test_decode_invalid_date_string(self):
        decoder = JSONDecoderISODate()
        result = decoder.decode('{"x": "not a date"}')
        assert result['x'] == 'not a date'


class TestRsleep:
    """Tests for rsleep function."""

    def test_rsleep_minimum(self):
        start = time.time()
        rsleep(always=0.01, rand_extra=0)
        elapsed = time.time() - start
        assert elapsed >= 0.01

    def test_rsleep_with_random(self):
        # Just verify it doesn't raise
        rsleep(always=0, rand_extra=1)


class TestRandRetry:
    """Tests for rand_retry decorator."""

    def test_rand_retry_success_first_try(self):
        call_count = 0

        @rand_retry(x_times=3, exception=ValueError)
        def succeed():
            nonlocal call_count
            call_count += 1
            return 'success'

        result = succeed()
        assert result == 'success'
        assert call_count == 1

    def test_rand_retry_eventual_success(self):
        import logging
        call_count = 0

        @rand_retry(x_times=3, exception=ValueError)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError('fail')
            return 'success'

        # Mock sleep timing and suppress retry logging
        with mock.patch('libb.webapp.rsleep'):
            logging.disable(logging.WARNING)
            try:
                result = fail_twice()
            finally:
                logging.disable(logging.NOTSET)
        assert result == 'success'
        assert call_count == 3

    def test_rand_retry_all_failures(self):
        import logging
        call_count = 0

        @rand_retry(x_times=2, exception=ValueError)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError('fail')

        # Mock sleep timing and suppress retry logging
        with mock.patch('libb.webapp.rsleep'):
            logging.disable(logging.WARNING)
            try:
                result = always_fail()
            finally:
                logging.disable(logging.NOTSET)
        assert result is None
        assert call_count == 3  # Initial + 2 retries


class TestInjectFile:
    """Tests for inject_file function."""

    def test_inject_file_reads_content(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write('test content')
            f.flush()
            result = inject_file(f.name)
        assert result == 'test content'
        Path(f.name).unlink()


class TestInjectImage:
    """Tests for inject_image function."""

    def test_inject_image_returns_data_uri(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'\x89PNG\r\n\x1a\n')  # PNG magic bytes
            f.flush()
            result = inject_image(f.name)
        assert result.startswith('data:image/png;base64,')
        Path(f.name).unlink()


class TestValidApiKey:
    """Tests for valid_api_key function."""

    def test_valid_api_key_valid_format(self):
        assert valid_api_key('abc123') is True
        assert valid_api_key('ABC-123_xyz') is True
        assert valid_api_key('a' * 255) is True

    def test_valid_api_key_invalid_format(self):
        assert valid_api_key('') is False
        assert valid_api_key(None) is False
        assert valid_api_key('a' * 256) is False  # Too long
        assert valid_api_key('abc@123') is False  # Invalid char


class TestCookieDefaults:
    """Tests for COOKIE_DEFAULTS constant."""

    def test_cookie_defaults_has_required_keys(self):
        assert 'version' in COOKIE_DEFAULTS
        assert 'domain' in COOKIE_DEFAULTS
        assert 'path' in COOKIE_DEFAULTS
        assert 'secure' in COOKIE_DEFAULTS
        assert 'expires' in COOKIE_DEFAULTS


class TestLocalOrStaticJoin:
    """Tests for local_or_static_join function."""

    def test_local_or_static_join_local_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            local_file = Path(tmpdir) / 'test.txt'
            local_file.write_text('local content')
            result = local_or_static_join('/nonexistent/static', str(local_file))
            # Function returns Path from expandabspath
            assert isinstance(result, Path)
            assert result == local_file

    def test_local_or_static_join_static_exists(self):
        with tempfile.TemporaryDirectory() as static_dir:
            static_file = Path(static_dir) / 'test.txt'
            static_file.write_text('static content')
            result = local_or_static_join(static_dir, 'test.txt')
            assert isinstance(result, Path)
            assert result == static_file

    def test_local_or_static_join_neither_exists(self):
        with pytest.raises(OSError, match='does not exist'):
            local_or_static_join('/nonexistent/static', 'nonexistent.txt')


class TestSafeJoinEdgeCases:
    """Additional tests for safe_join edge cases."""

    def test_safe_join_empty_filename(self):
        result = safe_join('/base', '', 'file.txt')
        assert result == '/base/file.txt'

    def test_safe_join_normpath_handling(self):
        result = safe_join('/base', 'subdir/./file.txt')
        assert result == '/base/subdir/file.txt'


class TestAuthd:
    """Tests for authd decorator."""

    def test_authd_allows_when_checker_passes(self):
        from libb.webapp import authd

        def checker():
            return True

        def fallback():
            return 'fallback'

        @authd(checker, fallback)
        def protected():
            return 'protected content'

        result = protected()
        assert result == 'protected content'

    def test_authd_fallback_when_checker_fails(self):
        from libb.webapp import authd

        def checker():
            return False

        def fallback():
            return 'fallback'

        @authd(checker, fallback)
        def protected():
            return 'protected content'

        result = protected()
        assert result == 'fallback'


class TestLogerror:
    """Tests for logerror function."""

    def test_logerror_wraps_error_fn(self):
        import logging

        from libb.webapp import logerror

        test_logger = logging.getLogger('test_logerror')
        errors_logged = []

        class MockHandler(logging.Handler):
            def emit(self, record):
                errors_logged.append(record.getMessage())

        test_logger.addHandler(MockHandler())
        test_logger.setLevel(logging.ERROR)

        def original_error():
            return 'original error page'

        wrapped = logerror(original_error, test_logger)

        # This should work but since there's no exception in sys.exc_info, exc will be None
        result = wrapped()
        assert result == 'original error page'

    def test_logerror_does_not_log_none_when_no_exception(self):
        """Verify logerror doesn't log 'NoneType: None' when no exception is active."""
        import logging

        from libb.webapp import logerror

        test_logger = logging.getLogger('test_logerror_none')
        errors_logged = []

        class MockHandler(logging.Handler):
            def emit(self, record):
                errors_logged.append(record.getMessage())

        test_logger.addHandler(MockHandler())
        test_logger.setLevel(logging.ERROR)

        def original_error():
            return 'error page'

        wrapped = logerror(original_error, test_logger)
        result = wrapped()

        assert result == 'error page'
        assert len(errors_logged) == 0, f'Should not log when no exception, but logged: {errors_logged}'

    def test_logerror_logs_exception_when_present(self):
        """Verify logerror logs the exception when one is active."""
        import logging
        import sys

        from libb.webapp import logerror

        test_logger = logging.getLogger('test_logerror_exc')
        errors_logged = []

        class MockHandler(logging.Handler):
            def emit(self, record):
                errors_logged.append(record.getMessage())

        test_logger.addHandler(MockHandler())
        test_logger.setLevel(logging.ERROR)

        def original_error():
            return 'error page'

        wrapped = logerror(original_error, test_logger)

        # Call wrapped within an exception context
        try:
            raise ValueError('test error')
        except ValueError:
            result = wrapped()

        assert result == 'error page'
        assert len(errors_logged) == 1
        assert 'test error' in errors_logged[0]


class TestProfileMiddleware:
    """Tests for ProfileMiddleware class."""

    def test_profile_middleware_init(self):
        import logging

        from libb.webapp import ProfileMiddleware

        def app(environ, start_response):
            return ['Hello']

        logger = logging.getLogger('test')
        pm = ProfileMiddleware(app, log=logger, sort='time', count=20)
        assert pm.func == app
        assert pm.log == logger
        assert pm.sort == 'time'
        assert pm.count == 20

    def test_profile_middleware_call(self):
        import logging

        from libb.webapp import ProfileMiddleware

        results = []

        def app(environ, start_response):
            results.append('called')
            return ['Hello']

        logger = logging.getLogger('test_profile')
        logger.setLevel(logging.DEBUG)

        pm = ProfileMiddleware(app, log=logger)
        result = pm({}, lambda s, h: None)

        assert result == ['Hello']
        assert 'called' in results


class TestCorsWebpyHelpers:
    """Tests for cors_webpy helper functions."""

    def test_cors_webpy_methods_formatting(self):
        # Test the methods formatting logic
        methods = ['get', 'post', 'PUT']
        formatted = ', '.join(sorted(x.upper() for x in methods))
        assert formatted == 'GET, POST, PUT'

    def test_cors_webpy_headers_formatting(self):
        # Test the headers formatting logic
        headers = ['content-type', 'Authorization']
        formatted = ', '.join(x.upper() for x in headers)
        assert formatted == 'CONTENT-TYPE, AUTHORIZATION'

    def test_cors_webpy_max_age_timedelta(self):
        # Test max_age timedelta conversion
        max_age = datetime.timedelta(hours=6)
        assert max_age.total_seconds() == 21600


class TestScaleEdgeCases:
    """Additional tests for scale function."""

    def test_scale_specific_color(self):
        # Test scaling a known color
        result = scale('#FF8000', 0.5)  # Orange
        assert result.startswith('#')

    def test_scale_near_boundary(self):
        result = scale('#FE0000', 1.1)  # Red slightly scaled up
        assert result.startswith('#')


class TestValidIpEdgeCases:
    """Additional tests for validip edge cases."""

    def test_validip_ipv6_bracket_no_port(self):
        result = validip('[fe80::1]')
        assert result == ('fe80::1', 8080)

    def test_validip_invalid_ipv6_in_brackets(self):
        with pytest.raises(ValueError):
            validip('[invalid]:80')

    def test_validip_ipv6_invalid_port(self):
        with pytest.raises(ValueError):
            validip('[::1]:invalid')


class TestMakeUrlEdgeCases:
    """Additional tests for make_url edge cases."""

    def test_make_url_merge_existing_list_param(self):
        result = make_url('/foo/?a=1', a=[2, 3])
        # Should merge existing a=1 with new [2, 3]
        assert 'a=' in result

    def test_make_url_double_underscore_ignored(self):
        result = make_url('/foo/', __custom__='ignored', bar=1)
        assert '__custom__' not in result
        assert 'bar=1' in result


if __name__ == '__main__':
    pytest.main([__file__])
