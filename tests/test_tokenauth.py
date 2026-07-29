"""Tests for the tokenauth module."""

import functools
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

    def test_active_client_returns_its_client_id(self):
        """Verify an active client resolves to its own client_id."""
        digest = tokenauth.hash_key('raw')
        stub = StubDynamo(items=[_item('c1', digest, active=True)])
        result = tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub)
        assert result == 'c1'
        assert result != digest
        assert result is not True

    def test_second_client_id_is_not_hardcoded(self):
        """Verify the returned identity tracks the matched row."""
        digest = tokenauth.hash_key('other')
        stub = StubDynamo(items=[_item('analyst-two', digest, active=True)])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) == 'analyst-two'

    def test_inactive_client_returns_none(self):
        """Verify a revoked client denies even though the row matches."""
        digest = tokenauth.hash_key('raw')
        stub = StubDynamo(items=[_item('c1', digest, active=False)])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is None

    def test_active_row_without_client_id_denies(self):
        """Verify an active but unattributable row is denied, not allowed."""
        digest = tokenauth.hash_key('raw')
        item = _item('c1', digest, active=True)
        del item['client_id']
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=StubDynamo(items=[item])) is None

    def test_missing_client_returns_none(self):
        """Verify an unknown key hash denies."""
        stub = StubDynamo(items=[])
        assert tokenauth.key_active_in_registry(
            'nope', table='t', dynamodb_client=stub) is None


class TestVerifyToken:
    """Tests for verify_token."""

    def test_static_token_yields_sentinel_not_the_credential(self):
        """Verify break-glass authorizes as a named identity, not the key."""
        result = tokenauth.verify_token('glass', static_token='glass')
        assert result == tokenauth.STATIC_TOKEN_CLIENT_ID
        assert result != 'glass'

    def test_static_token_mismatch_denies(self):
        """Verify a wrong static token does not authorize."""
        assert tokenauth.verify_token('nope', static_token='glass') is None

    def test_empty_presented_denies(self):
        """Verify an empty presented key is denied."""
        assert tokenauth.verify_token('', static_token='glass') is None

    def test_no_table_and_no_static_fails_closed(self):
        """Verify an unconfigured gate denies rather than opening."""
        assert tokenauth.verify_token('anything') is None

    def test_registry_path_returns_client_id(self):
        """Verify the registry path propagates the identity to the caller."""
        digest = tokenauth.hash_key('rawkey')
        stub = StubDynamo(items=[_item('c1', digest, active=True)])
        assert tokenauth.verify_token(
            'rawkey', table='t', dynamodb_client=stub) == 'c1'

    def test_registry_error_fails_closed(self):
        """Verify any registry error denies (fail closed)."""
        stub = StubDynamo(query_error=RuntimeError('boom'))
        assert tokenauth.verify_token(
            'rawkey', table='t', dynamodb_client=stub) is None


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

    def test_returns_sorted_client_records(self):
        """Verify list_clients returns sorted ClientRecord rows."""
        stub = StubDynamo(items=[
            _item('zeta', 'h1', active=True, created_at='2026-02-01'),
            _item('alpha', 'h2', active=False, created_at='2026-01-01'),
            ])
        rows = tokenauth.list_clients(table='t', dynamodb_client=stub)
        assert rows == [
            tokenauth.ClientRecord('alpha', 'revoked', '2026-01-01'),
            tokenauth.ClientRecord('zeta', 'active', '2026-02-01'),
            ]
        assert rows[0].status == 'revoked'


class TestRegistryCheckSeam:
    """Tests for the verify_token registry_check injection seam."""

    def test_registry_check_receives_digest_not_raw_key(self):
        """Verify registry_check is handed the digest, never the raw key."""
        seen = []
        check = lambda h: seen.append(h) or 'c1'
        tokenauth.verify_token('rawkey', registry_check=check)
        assert seen == [tokenauth.hash_key('rawkey')]
        assert 'rawkey' not in seen

    def test_registry_check_client_id_is_propagated(self):
        """Verify an identity-returning registry_check reaches the caller."""
        assert tokenauth.verify_token(
            'k', registry_check=lambda h: 'analyst-two') == 'analyst-two'

    def test_legacy_bool_registry_check_yields_sentinel(self):
        """Verify a bool-returning lookup authorizes without leaking True."""
        result = tokenauth.verify_token('k', registry_check=lambda h: True)
        assert result == tokenauth.UNKNOWN_CLIENT_ID
        assert result is not True

    def test_static_token_short_circuits_registry_check(self):
        """Verify the static token wins without consulting registry_check."""
        def _fail(h):
            raise AssertionError('registry_check should not run')
        assert tokenauth.verify_token(
            'glass', static_token='glass',
            registry_check=_fail) == tokenauth.STATIC_TOKEN_CLIENT_ID

    def test_registry_check_error_fails_closed(self):
        """Verify an error from registry_check denies."""
        def _boom(h):
            raise RuntimeError('cache down')
        assert tokenauth.verify_token('k', registry_check=_boom) is None


class TestPartialVerifier:
    """Verify functools.partial(verify_token, ...) wires a middleware verifier."""

    def test_partial_over_registry_check(self):
        """Verify a partial-bound verifier authorizes via registry_check."""
        verify = functools.partial(
            tokenauth.verify_token, registry_check=lambda h: 'c1')
        assert verify('anything') == 'c1'

    def test_partial_honors_static_token(self):
        """Verify a partial-bound verifier accepts the static token."""
        verify = functools.partial(tokenauth.verify_token, static_token='glass')
        assert verify('glass') == tokenauth.STATIC_TOKEN_CLIENT_ID
        assert verify('nope') is None


def _scope(path='/api/x', headers=None, query=b'', scheme='http'):
    """Build a minimal ASGI HTTP scope for middleware tests."""
    raw = [(k.encode('latin-1'), v.encode('latin-1'))
           for k, v in (headers or {}).items()]
    return {'type': scheme, 'path': path, 'headers': raw, 'query_string': query}


def _mw(verify=None, **kw):
    """Build an ApiTokenMiddleware with a no-op app and sane defaults."""
    kw.setdefault('protected_prefixes', ('/api/',))
    return tokenauth.ApiTokenMiddleware(
        app=None, verify=verify or (lambda k: True), **kw)


class TestPresentKey:
    """Tests for ApiTokenMiddleware key extraction precedence."""

    def test_x_api_key_header(self):
        """Verify the X-API-Key header is read."""
        assert _mw()._present_key(_scope(headers={'x-api-key': 'k1'})) == 'k1'

    def test_bearer_authorization(self):
        """Verify a Bearer authorization header yields the token."""
        assert _mw()._present_key(
            _scope(headers={'authorization': 'Bearer k2'})) == 'k2'

    def test_query_string_key_is_rejected(self):
        """Verify a ?key= query parameter is never accepted as a credential."""
        assert _mw()._present_key(_scope(query=b'key=k3')) is None

    def test_query_string_cannot_override_a_header(self):
        """Verify a query parameter cannot displace the header credential."""
        scope = _scope(headers={'x-api-key': 'k1'}, query=b'key=attacker')
        assert _mw()._present_key(scope) == 'k1'

    def test_x_api_key_wins_over_bearer(self):
        """Verify X-API-Key takes precedence over a Bearer header."""
        scope = _scope(headers={'x-api-key': 'k1', 'authorization': 'Bearer k2'})
        assert _mw()._present_key(scope) == 'k1'

    def test_empty_bearer_yields_none(self):
        """Verify a bare 'Bearer ' is not treated as a credential."""
        assert _mw()._present_key(
            _scope(headers={'authorization': 'Bearer '})) is None

    def test_missing_key_is_none(self):
        """Verify a request with no credential yields None."""
        assert _mw()._present_key(_scope()) is None


class TestGuards:
    """Tests for ApiTokenMiddleware._guards (which requests get gated)."""

    def test_protected_path_is_gated(self):
        """Verify a protected prefix engages the gate."""
        assert _mw()._guards(_scope(path='/api/x')) is True

    def test_unprotected_path_passes(self):
        """Verify a path outside the protected prefixes is not gated."""
        assert _mw()._guards(_scope(path='/health')) is False

    def test_non_http_passes(self):
        """Verify non-HTTP scopes (websocket/lifespan) are never gated."""
        assert _mw()._guards(_scope(path='/api/x', scheme='websocket')) is False

    def test_malformed_scope_passes(self):
        """Verify a scope missing 'type'/'path' passes through, not raises."""
        assert _mw()._guards({}) is False


def _run(mw, scope):
    """Drive the middleware once, capturing whether the app ran and any send()."""
    import asyncio
    sent = []
    app_ran = []

    async def app(s, r, sd):
        app_ran.append(True)

    async def send(msg):
        sent.append(msg)

    mw.app = app
    asyncio.run(mw(scope, None, send))
    return app_ran, sent


class TestCall:
    """Tests for the ApiTokenMiddleware ASGI __call__ gate."""

    def setup_method(self):
        """Skip the ASGI-gate tests when the anyio extra is absent."""
        pytest.importorskip('anyio')

    def test_authorized_request_reaches_app(self):
        """Verify a valid key lets the request through to the app."""
        mw = _mw(verify=lambda k: k == 'good')
        app_ran, sent = _run(mw, _scope(headers={'x-api-key': 'good'}))
        assert app_ran == [True]
        assert sent == []

    def test_unauthorized_request_gets_401(self):
        """Verify a bad key yields a raw-ASGI 401 and never reaches the app."""
        mw = _mw(verify=lambda k: False)
        app_ran, sent = _run(mw, _scope(headers={'x-api-key': 'bad'}))
        assert app_ran == []
        assert sent[0]['status'] == 401

    def test_verifier_exception_fails_closed(self):
        """Verify a raising verifier denies (401), not 500 or pass-through."""
        def _boom(k):
            raise RuntimeError('cache down')
        mw = _mw(verify=_boom)
        app_ran, sent = _run(mw, _scope(headers={'x-api-key': 'k'}))
        assert app_ran == []
        assert sent[0]['status'] == 401

    def test_unprotected_path_skips_verify(self):
        """Verify an open path reaches the app without calling verify."""
        mw = _mw(verify=lambda k: (_ for _ in ()).throw(AssertionError()))
        app_ran, _ = _run(mw, _scope(path='/health'))
        assert app_ran == [True]

    def test_authorized_scope_carries_client_id_not_the_key(self):
        """Verify the identity, never the credential, is published to scope."""
        mw = _mw(verify=lambda k: 'analyst-two')
        scope = _scope(headers={'x-api-key': 'secret-key'})
        app_ran, _ = _run(mw, scope)
        assert app_ran == [True]
        assert scope['state']['client_id'] == 'analyst-two'
        assert 'secret-key' not in scope['state'].values()

    def test_legacy_bool_verifier_publishes_sentinel(self):
        """Verify a bool-returning verifier yields a sentinel, not True."""
        mw = _mw(verify=lambda k: True)
        scope = _scope(headers={'x-api-key': 'k'})
        _run(mw, scope)
        assert scope['state']['client_id'] == tokenauth.UNKNOWN_CLIENT_ID

    def test_denied_request_publishes_no_identity(self):
        """Verify a rejected request leaves no client_id behind in scope."""
        mw = _mw(verify=lambda k: None)
        scope = _scope(headers={'x-api-key': 'bad'})
        app_ran, sent = _run(mw, scope)
        assert app_ran == []
        assert sent[0]['status'] == 401
        assert 'client_id' not in scope.get('state', {})

    def test_query_string_credential_is_not_accepted(self):
        """Verify a key supplied only in the query string yields a 401."""
        mw = _mw(verify=lambda k: 'c1')
        app_ran, sent = _run(mw, _scope(query=b'key=k3'))
        assert app_ran == []
        assert sent[0]['status'] == 401


class TestRunCli:
    """Tests for the run_cli admin command dispatch."""

    def test_add_prints_key_and_succeeds(self, capsys, monkeypatch):
        """Verify add mints a key, prints it, and returns 0."""
        monkeypatch.setattr(tokenauth, 'mint_key', lambda *a, **k: 'RAWKEY')
        rc = tokenauth.run_cli(['--table', 't', 'add', 'c1'])
        assert rc == 0
        assert 'RAWKEY' in capsys.readouterr().out

    def test_add_existing_returns_1(self, monkeypatch):
        """Verify add on an existing client returns exit code 1."""
        def _boom(*a, **k):
            raise tokenauth.ClientExistsError('c1')
        monkeypatch.setattr(tokenauth, 'mint_key', _boom)
        assert tokenauth.run_cli(['--table', 't', 'add', 'c1']) == 1

    def test_revoke_missing_returns_1(self, monkeypatch):
        """Verify revoke on an unknown client returns exit code 1."""
        def _boom(*a, **k):
            raise tokenauth.ClientNotFoundError('c1')
        monkeypatch.setattr(tokenauth, 'revoke_key', _boom)
        assert tokenauth.run_cli(['--table', 't', 'revoke', 'c1']) == 1

    def test_list_prints_rows(self, capsys, monkeypatch):
        """Verify list prints a row per client and returns 0."""
        monkeypatch.setattr(tokenauth, 'list_clients',
                            lambda *a, **k: [tokenauth.ClientRecord(
                                'c1', 'active', '2026-01-01')])
        rc = tokenauth.run_cli(['--table', 't', 'list'])
        assert rc == 0
        assert 'c1' in capsys.readouterr().out
