"""Tests for webapp web.py-specific functions."""

import datetime
import logging
import sys
from http.cookiejar import Cookie
from io import StringIO

import pytest

web = pytest.importorskip('web')

from libb import COOKIE_DEFAULTS, authd, cors_webpy


class TestCorsWebpy:
    """Tests for cors_webpy decorator."""

    def test_cors_webpy_adds_headers(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin=['mixpanel.com', 'mapbox.com'], methods=['GET', 'POST'], max_age=22)
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        headers = response.headers

        assert 'mixpanel.com' in headers.get('Access-Control-Allow-Origin', '')
        assert 'mapbox.com' in headers.get('Access-Control-Allow-Origin', '')
        assert headers.get('Access-Control-Allow-Credentials') == 'true'
        assert 'POST' in headers.get('Access-Control-Allow-Methods', '')
        assert headers.get('Access-Control-Max-Age') == '22'

    def test_cors_webpy_single_origin(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin='example.com')
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        assert 'example.com' in response.headers.get('Access-Control-Allow-Origin', '')


class TestAuthdWebpy:
    """Tests for authd decorator with web.py."""

    def test_authd_allows_with_cookie(self):
        urls = ('/(.*)', 'echo')

        def forbid():
            raise web.forbidden()

        @authd(lambda: web.cookies().get('allowed'), forbid)
        class echo:
            def GET(self, name):
                return name

        app = web.application(urls, {'echo': echo})
        b = app.browser()

        # Without cookie - forbidden
        response = b.open('/test')
        assert b'forbidden' in response.read()

        # With cookie - allowed
        allowed = Cookie(name='allowed', value='1', **COOKIE_DEFAULTS)
        b.cookiejar.set_cookie(allowed)
        response = b.open('/test')
        assert response.read() == b'test'

    def test_authd_on_specific_method(self):
        urls = ('/resource', 'resource_handler')

        def forbid():
            raise web.forbidden()

        class resource_handler:
            def GET(self):
                return 'get allowed'

            @authd(lambda: web.cookies().get('allowed'), forbid)
            def POST(self):
                return 'post allowed'

        app = web.application(urls, {'resource_handler': resource_handler})
        b = app.browser()

        # GET works without auth
        response = b.open('/resource')
        assert response.read() == b'get allowed'

        # POST without cookie - forbidden
        response = b.open('/resource', data={'x': 1})
        assert b'forbidden' in response.read()

        # POST with cookie - allowed
        allowed = Cookie(name='allowed', value='1', **COOKIE_DEFAULTS)
        b.cookiejar.set_cookie(allowed)
        response = b.open('/resource', data={'x': 1})
        assert response.read() == b'post allowed'


class TestAppmenu:
    """Tests for appmenu function."""

    def test_appmenu_basic(self):
        from libb import appmenu, splitcap

        urls = (
            'link/to/this/', 'this_thing',
            'another/', 'another',
        )
        result = appmenu(urls, '/subapp/', splitcap)
        assert '<ul class="menu">' in result
        assert '</ul>' in result
        assert '/subapp/link/to/this/' in result
        assert 'This Thing' in result
        assert '/subapp/another/' in result
        assert 'Another' in result

    def test_appmenu_with_home(self):
        from libb import appmenu

        urls = ('sec/', 'sec', 'cftc/', 'cftc')
        result = appmenu(urls, 'http://localhost:8081/ops/', lambda x: x.upper())
        assert 'http://localhost:8081/ops/sec/' in result
        assert 'SEC' in result
        assert 'CFTC' in result


class TestCorsWebpyOptions:
    """Tests for cors_webpy OPTIONS handling."""

    def test_cors_webpy_with_headers_string(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin='example.com', headers='X-Custom-Header')
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        headers = response.headers
        assert headers.get('Access-Control-Allow-Headers') == 'X-Custom-Header'

    def test_cors_webpy_with_headers_list(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin='example.com', headers=['X-Header-1', 'X-Header-2'])
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        headers = response.headers
        assert 'X-HEADER-1' in headers.get('Access-Control-Allow-Headers', '')
        assert 'X-HEADER-2' in headers.get('Access-Control-Allow-Headers', '')

    def test_cors_webpy_with_timedelta_max_age(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin='example.com', max_age=datetime.timedelta(hours=1))
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        headers = response.headers
        assert headers.get('Access-Control-Max-Age') == '3600.0'

    def test_cors_webpy_credentials_false(self):
        urls = ('/test', 'test_handler')

        @cors_webpy(None, origin='example.com', credentials=False)
        class test_handler:
            def GET(self):
                return 'OK'

        app = web.application(urls, {'test_handler': test_handler})
        b = app.browser()
        response = b.open('/test')
        headers = response.headers
        assert headers.get('Access-Control-Allow-Credentials') == 'false'


class TestLogerrorWebpy:
    """Tests for logerror function with web.py."""

    def test_logerror_logs_exception(self):
        from libb import logerror

        web.config.debug = False
        urls = ('/', 'error_handler')

        class error_handler:
            def GET(self):
                return None + 1  # TypeError

        app = web.application(urls, {'error_handler': error_handler})

        logger = logging.getLogger('LogTest')
        stderr = sys.stderr
        sys.stderr = mock_stream = StringIO()
        sh = logging.StreamHandler()
        sh.setLevel(logging.ERROR)
        logger.addHandler(sh)

        app.internalerror = logerror(app.internalerror, logger)

        b = app.browser()
        response = b.open('/')
        result = response.read()

        sys.stderr = stderr
        assert b'internal server error' in result.lower()
        logged_output = mock_stream.getvalue()
        assert 'TypeError' in logged_output
        mock_stream.close()


class TestRenderField:
    """Tests for render_field function."""

    def test_render_field_basic_input(self):
        from libb import render_field

        field = web.form.Textbox('name')
        result = render_field(field)
        assert '<input' in result

    def test_render_field_with_error(self):
        from libb import render_field

        field = web.form.Textbox('name')
        field.note = 'Required field'
        result = render_field(field)
        assert 'flderr' in result
        assert 'Required field' in result

    def test_render_field_django_style_errors(self):
        from libb import render_field

        class MockField:
            errors = ['Error 1', 'Error 2']

            def __str__(self):
                return '<input>'

        field = MockField()
        result = render_field(field)
        assert 'flderr' in result
        assert 'Error 1' in result

    def test_render_field_no_error(self):
        from libb import render_field

        class MockField:
            def __str__(self):
                return '<input>'

        field = MockField()
        result = render_field(field)
        assert 'flderr' not in result
        assert '<input>' in result


class TestProfileMiddleware:
    """Tests for ProfileMiddleware class."""

    def test_profile_middleware_basic(self):
        from webtest import TestApp

        from libb import ProfileMiddleware

        web.config.debug = False
        urls = ('/', 'profile_index')

        class profile_index:
            def GET(self):
                return 'Hello, world.'

        app = web.application(urls, {'profile_index': profile_index})

        log = logging.getLogger('ProfilerTest')
        log.setLevel(logging.DEBUG)
        mock_stream = StringIO()
        handler = logging.StreamHandler(mock_stream)
        log.addHandler(handler)

        profiled_app = ProfileMiddleware(app.wsgifunc(), log=log)
        t = TestApp(profiled_app)
        response = t.get('/')

        assert 'Hello' in response
        handler.flush()
        logged = mock_stream.getvalue()
        assert 'Run finished in' in logged
        assert 'Ordered by: internal time' in logged

    def test_profile_middleware_custom_sort(self):
        from webtest import TestApp

        from libb import ProfileMiddleware

        web.config.debug = False
        urls = ('/', 'profile_index2')

        class profile_index2:
            def GET(self):
                return 'Hello'

        app = web.application(urls, {'profile_index2': profile_index2})

        log = logging.getLogger('ProfilerTest2')
        log.setLevel(logging.DEBUG)
        mock_stream = StringIO()
        handler = logging.StreamHandler(mock_stream)
        log.addHandler(handler)

        profiled_app = ProfileMiddleware(app.wsgifunc(), log=log, sort='name', count=30)
        t = TestApp(profiled_app)
        t.get('/')

        handler.flush()
        logged = mock_stream.getvalue()
        assert 'Ordered by: function name' in logged


if __name__ == '__main__':
    pytest.main([__file__])
