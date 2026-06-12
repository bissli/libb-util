"""Tests for the tokenauth module."""

import hashlib

import pytest

from libb import tokenauth


class StubDynamo:
    """In-memory boto3 DynamoDB client stub for tokenauth tests."""

    def __init__(self, items=None, query_error=None, put_error=None,
                 update_error=None):
        self.items = items or []
        self.query_error = query_error
        self.put_error = put_error
        self.update_error = update_error
        self.put_calls = []
        self.update_calls = []

    def query(self, **kwargs):
        if self.query_error:
            raise self.query_error
        target = kwargs['ExpressionAttributeValues'][':h']['S']
        matches = [i for i in self.items
                   if i.get('key_sha256', {}).get('S') == target]
        return {'Items': matches[:1]}

    def put_item(self, **kwargs):
        if self.put_error:
            raise self.put_error
        self.put_calls.append(kwargs)

    def update_item(self, **kwargs):
        if self.update_error:
            raise self.update_error
        self.update_calls.append(kwargs)

    def get_paginator(self, name):
        items = self.items

        class _Paginator:
            def paginate(self, **kwargs):
                return [{'Items': items}]

        return _Paginator()


def _item(client_id, key_sha256, active=True,
          created_at='2026-01-01T00:00:00+00:00'):
    return {
        'client_id': {'S': client_id},
        'client_name': {'S': client_id},
        'key_sha256': {'S': key_sha256},
        'active': {'BOOL': active},
        'created_at': {'S': created_at},
        }


def _conditional_error():
    """Build a botocore ConditionalCheckFailed ClientError."""
    from botocore.exceptions import ClientError
    return ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'x'}},
        'Operation')


class TestHashKey:
    """Tests for hash_key."""

    def test_matches_sha256_hexdigest(self):
        """Verify hash_key returns the SHA-256 hex digest of the raw key."""
        assert tokenauth.hash_key('secret') == hashlib.sha256(b'secret').hexdigest()


class TestKeyActiveInRegistry:
    """Tests for key_active_in_registry."""

    def test_active_client_returns_true(self):
        """Verify an active matching client reads as active."""
        digest = tokenauth.hash_key('raw')
        stub = StubDynamo(items=[_item('c1', digest, active=True)])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is True

    def test_inactive_client_returns_false(self):
        """Verify a revoked (inactive) client reads as not active."""
        digest = tokenauth.hash_key('raw')
        stub = StubDynamo(items=[_item('c1', digest, active=False)])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is False

    def test_missing_client_returns_false(self):
        """Verify an unknown key hash reads as not active."""
        stub = StubDynamo(items=[])
        assert tokenauth.key_active_in_registry(
            'nope', table='t', dynamodb_client=stub) is False


class TestVerifyToken:
    """Tests for verify_token."""

    def test_static_token_constant_time_match(self):
        """Verify a correct static break-glass token authorizes."""
        assert tokenauth.verify_token('glass', static_token='glass') is True

    def test_static_token_mismatch_denies(self):
        """Verify a wrong static token does not authorize."""
        assert tokenauth.verify_token('nope', static_token='glass') is False

    def test_empty_presented_denies(self):
        """Verify an empty presented key is denied."""
        assert tokenauth.verify_token('', static_token='glass') is False

    def test_no_table_and_no_static_fails_closed(self):
        """Verify an unconfigured gate denies rather than opening."""
        assert tokenauth.verify_token('anything') is False

    def test_registry_active_authorizes(self):
        """Verify a presented key whose hash is an active client authorizes."""
        digest = tokenauth.hash_key('rawkey')
        stub = StubDynamo(items=[_item('c1', digest, active=True)])
        assert tokenauth.verify_token(
            'rawkey', table='t', dynamodb_client=stub) is True

    def test_registry_error_fails_closed(self):
        """Verify any registry error denies (fail closed)."""
        stub = StubDynamo(query_error=RuntimeError('boom'))
        assert tokenauth.verify_token(
            'rawkey', table='t', dynamodb_client=stub) is False


class TestMintKey:
    """Tests for mint_key."""

    def test_returns_raw_key_and_stores_hash(self):
        """Verify mint_key returns the raw key and stores only its hash."""
        pytest.importorskip('botocore')
        stub = StubDynamo()
        raw = tokenauth.mint_key('c1', table='t', dynamodb_client=stub)
        item = stub.put_calls[0]['Item']
        assert item['key_sha256']['S'] == tokenauth.hash_key(raw)
        assert item['client_id']['S'] == 'c1'
        assert item['active']['BOOL'] is True
        assert stub.put_calls[0]['ConditionExpression'] == 'attribute_not_exists(client_id)'

    def test_force_omits_condition(self):
        """Verify force rotation writes without the existence guard."""
        pytest.importorskip('botocore')
        stub = StubDynamo()
        tokenauth.mint_key('c1', table='t', force=True, dynamodb_client=stub)
        assert 'ConditionExpression' not in stub.put_calls[0]

    def test_existing_client_raises(self):
        """Verify minting an existing client raises ClientExistsError."""
        pytest.importorskip('botocore')
        stub = StubDynamo(put_error=_conditional_error())
        with pytest.raises(tokenauth.ClientExistsError):
            tokenauth.mint_key('c1', table='t', dynamodb_client=stub)


class TestRevokeKey:
    """Tests for revoke_key."""

    def test_clears_active_flag(self):
        """Verify revoke_key updates the client to inactive."""
        pytest.importorskip('botocore')
        stub = StubDynamo()
        tokenauth.revoke_key('c1', table='t', dynamodb_client=stub)
        call = stub.update_calls[0]
        assert call['ExpressionAttributeValues'][':f']['BOOL'] is False
        assert call['Key']['client_id']['S'] == 'c1'

    def test_missing_client_raises(self):
        """Verify revoking an unknown client raises ClientNotFoundError."""
        pytest.importorskip('botocore')
        stub = StubDynamo(update_error=_conditional_error())
        with pytest.raises(tokenauth.ClientNotFoundError):
            tokenauth.revoke_key('c1', table='t', dynamodb_client=stub)


class TestListClients:
    """Tests for list_clients."""

    def test_returns_sorted_status_rows(self):
        """Verify list_clients returns sorted (id, status, created_at) tuples."""
        stub = StubDynamo(items=[
            _item('zeta', 'h1', active=True, created_at='2026-02-01'),
            _item('alpha', 'h2', active=False, created_at='2026-01-01'),
            ])
        rows = tokenauth.list_clients(table='t', dynamodb_client=stub)
        assert rows == [
            ('alpha', 'revoked', '2026-01-01'),
            ('zeta', 'active', '2026-02-01'),
            ]


def _scope(path='/api/x', headers=None, query=b'', scheme='http'):
    """Build a minimal ASGI HTTP scope for middleware tests."""
    raw = [(k.encode('latin-1'), v.encode('latin-1'))
           for k, v in (headers or {}).items()]
    return {'type': scheme, 'path': path, 'headers': raw, 'query_string': query}


def _mw(**kw):
    """Build an ApiTokenMiddleware with a no-op app and sane defaults."""
    kw.setdefault('protected_prefixes', ('/api/',))
    return tokenauth.ApiTokenMiddleware(app=None, **kw)


class TestPresentKey:
    """Tests for ApiTokenMiddleware key extraction precedence."""

    def test_x_api_key_header(self):
        """Verify the X-API-Key header is read."""
        assert _mw()._present_key(_scope(headers={'x-api-key': 'k1'})) == 'k1'

    def test_bearer_authorization(self):
        """Verify a Bearer authorization header yields the token."""
        assert _mw()._present_key(
            _scope(headers={'authorization': 'Bearer k2'})) == 'k2'

    def test_query_param_fallback(self):
        """Verify ?key= is used when no header carries a key."""
        assert _mw()._present_key(_scope(query=b'key=k3')) == 'k3'

    def test_x_api_key_wins_over_bearer(self):
        """Verify X-API-Key takes precedence over a Bearer header."""
        scope = _scope(headers={'x-api-key': 'k1', 'authorization': 'Bearer k2'})
        assert _mw()._present_key(scope) == 'k1'

    def test_missing_key_is_none(self):
        """Verify a request with no credential yields None."""
        assert _mw()._present_key(_scope()) is None


class TestGuards:
    """Tests for ApiTokenMiddleware._guards (which requests get gated)."""

    def test_protected_path_is_gated(self):
        """Verify a configured gate engages on a protected prefix."""
        assert _mw(static_token='t')._guards(_scope(path='/api/x')) is True

    def test_unprotected_path_passes(self):
        """Verify a path outside the protected prefixes is not gated."""
        assert _mw(static_token='t')._guards(_scope(path='/health')) is False

    def test_unconfigured_gate_passes(self):
        """Verify a gate with no token, table, or verifier never engages."""
        assert _mw()._guards(_scope(path='/api/x')) is False

    def test_non_http_passes(self):
        """Verify non-HTTP scopes (websocket/lifespan) are never gated."""
        assert _mw(static_token='t')._guards(
            _scope(path='/api/x', scheme='websocket')) is False


class TestAuthorize:
    """Tests for ApiTokenMiddleware._authorize dispatch."""

    def test_injected_verifier_used(self):
        """Verify an injected verify callable overrides verify_token."""
        seen = []
        mw = _mw(verify=lambda k: seen.append(k) or k == 'ok')
        assert mw._authorize('ok') is True
        assert mw._authorize('no') is False
        assert seen == ['ok', 'no']

    def test_default_uses_static_token(self):
        """Verify the default authorizer honors the static break-glass token."""
        assert _mw(static_token='glass')._authorize('glass') is True
        assert _mw(static_token='glass')._authorize('wrong') is False


class TestAdminMain:
    """Tests for the _admin_main CLI dispatch."""

    def test_add_prints_key_and_succeeds(self, capsys, monkeypatch):
        """Verify add mints a key, prints it, and returns 0."""
        monkeypatch.setattr(tokenauth, 'mint_key', lambda *a, **k: 'RAWKEY')
        rc = tokenauth._admin_main(['--table', 't', 'add', 'c1'])
        assert rc == 0
        assert 'RAWKEY' in capsys.readouterr().out

    def test_add_existing_returns_1(self, monkeypatch):
        """Verify add on an existing client returns exit code 1."""
        def _boom(*a, **k):
            raise tokenauth.ClientExistsError('c1')
        monkeypatch.setattr(tokenauth, 'mint_key', _boom)
        assert tokenauth._admin_main(['--table', 't', 'add', 'c1']) == 1

    def test_revoke_missing_returns_1(self, monkeypatch):
        """Verify revoke on an unknown client returns exit code 1."""
        def _boom(*a, **k):
            raise tokenauth.ClientNotFoundError('c1')
        monkeypatch.setattr(tokenauth, 'revoke_key', _boom)
        assert tokenauth._admin_main(['--table', 't', 'revoke', 'c1']) == 1

    def test_list_prints_rows(self, capsys, monkeypatch):
        """Verify list prints a row per client and returns 0."""
        monkeypatch.setattr(tokenauth, 'list_clients',
                            lambda *a, **k: [('c1', 'active', '2026-01-01')])
        rc = tokenauth._admin_main(['--table', 't', 'list'])
        assert rc == 0
        assert 'c1' in capsys.readouterr().out
