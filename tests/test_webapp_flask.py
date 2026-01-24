"""Tests for webapp Flask-specific functions."""

import pytest

flask = pytest.importorskip('flask')

from libb import authd, cors_flask, get_cntc, get_current_session
from libb import get_request_context, get_request_dict, get_session


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


class TestGetCntc:
    """Tests for get_cntc function."""

    def test_get_cntc_from_flask_g(self):
        """Verify get_cntc retrieves value from flask.g."""
        app = flask.Flask(__name__)

        class MockConnection:
            name = 'test_connection'

        @app.route('/test')
        def test_route():
            flask.g.cntc = MockConnection()
            cntc = get_cntc()
            return cntc.name

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'test_connection'


class TestGetSession:
    """Tests for get_session and get_current_session functions."""

    def test_get_session_from_beaker_environ(self):
        """Verify get_session retrieves Beaker session from environ."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            flask.request.environ['beaker.session'] = {'user': 'testuser'}
            session = get_session()
            return session.get('user', 'none')

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'testuser'

    def test_get_current_session_same_as_get_session(self):
        """Verify get_current_session returns same as get_session."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            flask.request.environ['beaker.session'] = {'groups': ['admin']}
            session1 = get_session()
            session2 = get_current_session()
            return 'match' if session1 == session2 else 'mismatch'

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'match'

    def test_get_session_empty_when_no_beaker(self):
        """Verify get_session returns empty dict when no Beaker session."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            session = get_session()
            return 'empty' if session == {} else 'not_empty'

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'empty'


class TestGetRequestContext:
    """Tests for get_request_context function."""

    def test_get_request_context_returns_flask_g(self):
        """Verify get_request_context returns flask.g in Flask context."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            ctx = get_request_context()
            ctx.test_value = 'hello'
            return flask.g.test_value

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'hello'

    def test_get_request_context_attributes_persist(self):
        """Verify attributes set on context persist within request."""
        app = flask.Flask(__name__)

        @app.route('/test')
        def test_route():
            ctx = get_request_context()
            ctx.cntc = 'db_connection'
            ctx.user = 'admin'
            return f'{flask.g.cntc}:{flask.g.user}'

        client = app.test_client()
        response = client.get('/test')
        assert response.data == b'db_connection:admin'


if __name__ == '__main__':
    pytest.main([__file__])
