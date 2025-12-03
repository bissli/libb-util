"""Tests for webapp Flask-specific functions."""

import pytest

flask = pytest.importorskip('flask')

from libb import authd, cors_flask


class TestCorsFlask:
    """Tests for cors_flask decorator."""

    def test_cors_flask_adds_headers(self):
        app = flask.Flask(__name__)

        @app.route('/test')
        @cors_flask(app, origin=['example.com'], methods=['GET', 'POST'], max_age=100)
        def test_route():
            return 'OK'

        client = app.test_client()
        response = client.get('/test')
        assert response.status_code == 200
        assert 'example.com' in response.headers.get('Access-Control-Allow-Origin', '')
        assert 'GET' in response.headers.get('Access-Control-Allow-Methods', '')
        assert 'POST' in response.headers.get('Access-Control-Allow-Methods', '')
        assert response.headers.get('Access-Control-Max-Age') == '100'

    def test_cors_flask_credentials(self):
        app = flask.Flask(__name__)

        @app.route('/test')
        @cors_flask(app, origin='example.com', credentials=True)
        def test_route():
            return 'OK'

        client = app.test_client()
        response = client.get('/test')
        assert response.headers.get('Access-Control-Allow-Credentials') == 'true'

    def test_cors_flask_multiple_origins(self):
        app = flask.Flask(__name__)

        @app.route('/test')
        @cors_flask(app, origin=['site1.com', 'site2.com'])
        def test_route():
            return 'OK'

        client = app.test_client()
        response = client.get('/test')
        origin_header = response.headers.get('Access-Control-Allow-Origin', '')
        assert 'site1.com' in origin_header
        assert 'site2.com' in origin_header


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


if __name__ == '__main__':
    pytest.main([__file__])
