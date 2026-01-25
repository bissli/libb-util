"""Tests for webapp utility functions."""

import datetime
import logging
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

import pytest

from libb import COOKIE_DEFAULTS, JSONDecoderISODate, JSONEncoderISODate
from libb import appmenu, htmlquote, inject_file, inject_image, local_or_static_join
from libb import make_url, rand_retry, render_field, rsleep, safe_join, scale, websafe


class TestHtmlQuote:
    """Tests for htmlquote function."""

    def test_htmlquote_special_chars(self):
        assert htmlquote("<'&\">") == '&lt;&#39;&amp;&quot;&gt;'

    def test_htmlquote_ampersand_first(self):
        assert htmlquote('&lt;') == '&amp;lt;'

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


class TestRenderField:
    """Tests for render_field function."""

    def test_render_field_basic(self):
        """Verify basic field rendering."""
        class MockField:
            def __str__(self):
                return '<input type="text" name="test">'
        result = render_field(MockField())
        assert '<input type="text" name="test">' in result

    def test_render_field_with_note_error(self):
        """Verify field with note error wraps in error span."""
        class MockField:
            note = 'Field is required'
            def __str__(self):
                return '<input type="text">'
        result = render_field(MockField())
        assert '<span class="flderr" title="Field is required">' in result
        assert '</span>' in result

    def test_render_field_with_errors_list(self):
        """Verify field with errors list wraps in error span."""
        class MockField:
            errors = ['Error 1', 'Error 2']
            def __str__(self):
                return '<input type="text">'
        result = render_field(MockField())
        assert '<span class="flderr" title="Error 1, Error 2">' in result

    def test_render_field_no_error(self):
        """Verify field without error has no error span."""
        class MockField:
            def __str__(self):
                return '<input type="text">'
        result = render_field(MockField())
        assert 'flderr' not in result
        assert '<input type="text">' in result


class TestAppmenu:
    """Tests for appmenu function."""

    def test_appmenu_basic(self):
        """Verify basic menu generation with URL/name pairs."""
        result = appmenu(('/path1/', 'name_one', '/path2/', 'name_two'))
        assert '<ul class="menu">' in result
        assert '<li><a href="/path1/">Name One</a></li>' in result
        assert '<li><a href="/path2/">Name Two</a></li>' in result
        assert '</ul>' in result

    def test_appmenu_preserves_urls(self):
        """Verify URLs are used as-is without modification."""
        result = appmenu(('/trading/top_n_pnl/', 'top_n_pnl'))
        assert 'href="/trading/top_n_pnl/"' in result

    def test_appmenu_custom_formatter(self):
        """Verify custom formatter is applied to names."""
        result = appmenu(('/path/', 'test_name'), fmt_name=str.upper)
        assert 'TEST_NAME' in result

    def test_appmenu_empty(self):
        """Verify empty tuple produces empty menu."""
        result = appmenu(())
        assert result == '<ul class="menu">\n\n</ul>'


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


class TestSafeJoin:
    """Tests for safe_join function."""

    def test_safe_join_basic(self):
        result = safe_join('/base', 'subdir', 'file.txt')
        assert result == '/base/subdir/file.txt'

    def test_safe_join_blocks_traversal(self):
        assert safe_join('/base', '../etc/passwd') is None
        assert safe_join('/base', 'foo/../../../etc/passwd') is None

    @pytest.mark.skipif(sys.platform == 'win32', reason='Unix absolute paths not recognized on Windows')
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
        assert '80' in result or '7F' in result

    def test_scale_hex3(self):
        result = scale('#FFF', 0.5)
        assert result.startswith('#')

    def test_scale_black(self):
        result = scale('#000000', 2.0)
        assert result == '#000'

    def test_scale_clamps(self):
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
        call_count = 0

        @rand_retry(x_times=3, exception=ValueError)
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError('fail')
            return 'success'

        with mock.patch('libb.webapp.rsleep'):
            logging.disable(logging.WARNING)
            try:
                result = fail_twice()
            finally:
                logging.disable(logging.NOTSET)
        assert result == 'success'
        assert call_count == 3

    def test_rand_retry_all_failures(self):
        call_count = 0

        @rand_retry(x_times=2, exception=ValueError)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError('fail')

        with mock.patch('libb.webapp.rsleep'):
            logging.disable(logging.WARNING)
            try:
                result = always_fail()
            finally:
                logging.disable(logging.NOTSET)
        assert result is None
        assert call_count == 3


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
            f.write(b'\x89PNG\r\n\x1a\n')
            f.flush()
            result = inject_image(f.name)
        assert result.startswith('data:image/png;base64,')
        Path(f.name).unlink()


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
            assert isinstance(result, Path)
            assert result.resolve() == local_file.resolve()

    def test_local_or_static_join_static_exists(self):
        with tempfile.TemporaryDirectory() as static_dir:
            static_file = Path(static_dir) / 'test.txt'
            static_file.write_text('static content')
            result = local_or_static_join(static_dir, 'test.txt')
            assert isinstance(result, Path)
            assert result.resolve() == static_file.resolve()

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
        result = wrapped()
        assert result == 'original error page'

    def test_logerror_does_not_log_none_when_no_exception(self):
        """Verify logerror doesn't log 'NoneType: None' when no exception."""
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
        from libb.webapp import ProfileMiddleware

        results = []

        def app(environ, start_response):
            results.append('called')
            return ['Hello']

        logger = logging.getLogger('test_profile')
        logger.setLevel(logging.DEBUG)

        pm = ProfileMiddleware(app, log=logger)
        try:
            result = pm({}, lambda s, h: None)
        except ValueError as e:
            if 'Another profiling tool is already active' in str(e):
                pytest.skip('cProfile conflict with another profiler')
            raise

        assert result == ['Hello']
        assert 'called' in results


class TestScaleEdgeCases:
    """Additional tests for scale function."""

    def test_scale_specific_color(self):
        result = scale('#FF8000', 0.5)
        assert result.startswith('#')

    def test_scale_near_boundary(self):
        result = scale('#FE0000', 1.1)
        assert result.startswith('#')


class TestMakeUrlEdgeCases:
    """Additional tests for make_url edge cases."""

    def test_make_url_merge_existing_list_param(self):
        result = make_url('/foo/?a=1', a=[2, 3])
        assert 'a=' in result

    def test_make_url_double_underscore_ignored(self):
        result = make_url('/foo/', __custom__='ignored', bar=1)
        assert '__custom__' not in result
        assert 'bar=1' in result


class TestJinja2Render:
    """Tests for Jinja2Render class."""

    def test_jinja2_render_basic(self):
        """Verify basic template rendering works."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('Hello {{ name }}!')

            render = Jinja2Render(tmpdir)
            result = render('test.html', name='World')
            assert result == 'Hello World!'

    def test_jinja2_render_with_globals(self):
        """Verify globals are accessible in templates."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('Today is {{ today() }}')

            render = Jinja2Render(tmpdir, globals={'today': lambda: '2024-01-01'})
            result = render('test.html')
            assert result == 'Today is 2024-01-01'

    def test_jinja2_render_add_globals(self):
        """Verify add_globals method works."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('Value: {{ custom_func() }}')

            render = Jinja2Render(tmpdir)
            render.add_globals({'custom_func': lambda: 42})
            result = render('test.html')
            assert result == 'Value: 42'

    def test_jinja2_render_add_filter(self):
        """Verify add_filter method works."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('{{ name|upper_custom }}')

            render = Jinja2Render(tmpdir)
            render.add_filter('upper_custom', lambda s: s.upper())
            result = render('test.html', name='hello')
            assert result == 'HELLO'

    def test_jinja2_render_autoescape(self):
        """Verify autoescaping works by default."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('{{ content }}')

            render = Jinja2Render(tmpdir)
            result = render('test.html', content='<script>alert("xss")</script>')
            assert '&lt;script&gt;' in result
            assert '<script>' not in result

    def test_jinja2_render_safe_filter(self):
        """Verify safe filter bypasses autoescaping."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('{{ content|safe }}')

            render = Jinja2Render(tmpdir)
            result = render('test.html', content='<b>bold</b>')
            assert result == '<b>bold</b>'

    def test_jinja2_render_extends(self):
        """Verify template inheritance works."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / 'base.html'
            base_path.write_text('<html>{% block content %}{% endblock %}</html>')

            child_path = Path(tmpdir) / 'child.html'
            child_path.write_text(
                '{% extends "base.html" %}{% block content %}Hello{% endblock %}'
            )

            render = Jinja2Render(tmpdir)
            result = render('child.html')
            assert result == '<html>Hello</html>'

    def test_jinja2_render_macro(self):
        """Verify macros work in templates."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text(
                '{% macro greet(name) %}Hello {{ name }}!{% endmacro %}{{ greet("World") }}'
            )

            render = Jinja2Render(tmpdir)
            result = render('test.html')
            assert result == 'Hello World!'

    def test_jinja2_render_for_loop(self):
        """Verify for loops work in templates."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('{% for item in items %}{{ item }},{% endfor %}')

            render = Jinja2Render(tmpdir)
            result = render('test.html', items=['a', 'b', 'c'])
            assert result == 'a,b,c,'

    def test_jinja2_render_if_condition(self):
        """Verify if conditions work in templates."""
        from libb.webapp import Jinja2Render

        with tempfile.TemporaryDirectory() as tmpdir:
            template_path = Path(tmpdir) / 'test.html'
            template_path.write_text('{% if show %}visible{% else %}hidden{% endif %}')

            render = Jinja2Render(tmpdir)
            assert render('test.html', show=True) == 'visible'
            assert render('test.html', show=False) == 'hidden'


flask = pytest.importorskip('flask')

from libb import authd, external_url_for, get_request_dict, is_safe_redirect_url


class TestAuthdFlask:
    """Tests for authd decorator with Flask."""

    def test_authd_allows_when_checker_passes(self):
        app = flask.Flask(__name__)

        @app.route('/restricted')
        @authd(lambda: flask.request.cookies.get('allowed'), lambda: flask.abort(403))
        def restricted():
            return 'secret'

        client = app.test_client()
        client.set_cookie('allowed', '1')
        response = client.get('/restricted')
        assert response.status_code == 200
        assert response.data == b'secret'

    def test_authd_denies_when_checker_fails(self):
        app = flask.Flask(__name__)

        @app.route('/restricted')
        @authd(lambda: flask.request.cookies.get('allowed'), lambda: flask.abort(403))
        def restricted():
            return 'secret'

        client = app.test_client()
        response = client.get('/restricted')
        assert response.status_code == 403

    def test_authd_with_custom_fallback(self):
        app = flask.Flask(__name__)

        @app.route('/restricted')
        @authd(lambda: False, lambda: ('denied', 401))
        def restricted():
            return 'secret'

        client = app.test_client()
        response = client.get('/restricted')
        assert response.status_code == 401
        assert b'denied' in response.data


class TestGetRequestDict:
    """Tests for get_request_dict function."""

    def test_get_request_dict_with_defaults(self):
        """Verify defaults are applied when params not provided."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            req = get_request_dict(fund='All', limit=10)
            return flask.jsonify(req)

        client = app.test_client()
        response = client.get('/test')
        data = response.get_json()
        assert data['fund'] == 'All'
        assert data['limit'] == 10

    def test_get_request_dict_with_query_params(self):
        """Verify query params override defaults."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            req = get_request_dict(fund='All', limit=10)
            return flask.jsonify(req)

        client = app.test_client()
        response = client.get('/test?fund=Tenor&limit=50')
        data = response.get_json()
        assert data['fund'] == 'Tenor'
        assert data['limit'] == '50'

    def test_get_request_dict_with_callable_defaults(self):
        """Verify callable defaults are invoked."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            req = get_request_dict(value=lambda: 42)
            return flask.jsonify(req)

        client = app.test_client()
        response = client.get('/test')
        data = response.get_json()
        assert data['value'] == 42

    def test_get_request_dict_callable_not_called_when_param_provided(self):
        """Verify callable defaults not called when param is provided."""
        app = flask.Flask(__name__)
        call_count = [0]

        def counter():
            call_count[0] += 1
            return 'default'

        @app.route('/test')
        def test_route():
            req = get_request_dict(value=counter)
            return flask.jsonify(req)

        client = app.test_client()
        response = client.get('/test?value=provided')
        data = response.get_json()
        assert data['value'] == 'provided'
        assert call_count[0] == 0

    def test_get_request_dict_empty_string_uses_default(self):
        """Verify empty string param triggers default."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            req = get_request_dict(value='default')
            return flask.jsonify(req)

        client = app.test_client()
        response = client.get('/test?value=')
        data = response.get_json()
        assert data['value'] == 'default'

    def test_get_request_dict_post_form_data(self):
        """Verify form data is captured from POST."""
        app = flask.Flask(__name__)

        @app.route('/test', methods=['POST'])
        def test_route():
            req = get_request_dict(fund='All')
            return flask.jsonify(req)

        client = app.test_client()
        response = client.post('/test', data={'fund': 'Tenor', 'amount': '100'})
        data = response.get_json()
        assert data['fund'] == 'Tenor'
        assert data['amount'] == '100'


class TestIsSafeRedirectUrl:
    """Tests for is_safe_redirect_url function."""

    def test_safe_relative_path(self):
        """Verify relative paths starting with / are safe."""
        assert is_safe_redirect_url('/dashboard') is True
        assert is_safe_redirect_url('/path/to/page') is True
        assert is_safe_redirect_url('/') is True

    def test_unsafe_protocol_injection(self):
        """Verify protocol-relative URLs are blocked."""
        assert is_safe_redirect_url('//evil.com/path') is False

    def test_unsafe_absolute_url(self):
        """Verify absolute URLs are blocked."""
        assert is_safe_redirect_url('https://evil.com') is False
        assert is_safe_redirect_url('http://evil.com') is False

    def test_unsafe_empty_or_none(self):
        """Verify empty and None values are blocked."""
        assert is_safe_redirect_url('') is False
        assert is_safe_redirect_url(None) is False

    def test_unsafe_relative_without_slash(self):
        """Verify paths not starting with / are blocked."""
        assert is_safe_redirect_url('path/to/page') is False
        assert is_safe_redirect_url('dashboard') is False


class TestExternalUrlFor:
    """Tests for external_url_for function."""

    def test_external_url_basic(self):
        """Verify basic URL generation with base URL."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            return 'test'

        with app.test_request_context():
            result = external_url_for('https://app.example.com', 'test_route')
            assert result == 'https://app.example.com/test'

    def test_external_url_with_params(self):
        """Verify URL parameters are included."""
        app = flask.Flask(__name__)

        @app.route('/user/<int:user_id>')
        def user_detail(user_id):
            return f'User {user_id}'

        with app.test_request_context():
            result = external_url_for('https://app.example.com', 'user_detail', user_id=123)
            assert result == 'https://app.example.com/user/123'

    def test_external_url_with_trailing_slash(self):
        """Verify trailing slash on base URL is handled."""
        app = flask.Flask(__name__)

        @app.route('/page')
        def page():
            return 'page'

        with app.test_request_context():
            result = external_url_for('https://app.example.com/', 'page')
            assert result == 'https://app.example.com/page'


if __name__ == '__main__':
    pytest.main([__file__])
