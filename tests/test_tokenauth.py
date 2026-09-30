"""Tests for the tokenauth module."""

import datetime
import functools
import hashlib
import logging

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
          created_at='2026-01-01T00:00:00+00:00', expires_at=None):
    item = {
        'client_id': {'S': client_id},
        'client_name': {'S': client_id},
        'key_sha256': {'S': key_sha256},
        'active': {'BOOL': active},
        'created_at': {'S': created_at},
        }
    if expires_at is not None:
        item['expires_at'] = {'S': expires_at}
    return item


def _offset_iso(hours, tz=datetime.timezone.utc, suffix=None):
    """Return an ISO-8601 stamp `hours` from now, for expiry fixtures."""
    moment = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
        hours=hours)
    if suffix == 'Z':
        return moment.replace(tzinfo=None).isoformat() + 'Z'
    if tz is None:
        return moment.replace(tzinfo=None).isoformat()
    return moment.astimezone(tz).isoformat()


def _conditional_error():
    """Build a botocore ConditionalCheckFailed ClientError."""
    from botocore.exceptions import ClientError
    return ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'x'}},
        'Operation')


@pytest.fixture
def tokenauth_warnings():
    """WARNING records libb.tokenauth logs during a test, as (level, message).

    The suite runs with ``-p no:logging``, which disables ``caplog``.
    """
    records = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            records.append((record.levelname, record.getMessage()))

    handler = ListHandler(level=logging.WARNING)
    tokenauth_logger = logging.getLogger('libb.tokenauth')
    tokenauth_logger.addHandler(handler)
    yield records
    tokenauth_logger.removeHandler(handler)


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

    def test_expired_key_denies_and_live_key_authorizes(self):
        """Verify the expiry comparison refuses past and admits future.

        Mutation: the expiry comparison flipped (`expiry <= now` to
            `expiry >= now`), which authorizes every stale key and
            refuses every live one.
        Oracle: two rows straddling now by one hour either side, so a
            flipped comparison swaps both assertions at once.
        """
        digest = hashlib.sha256(b'live').hexdigest()
        stale = hashlib.sha256(b'stale').hexdigest()
        stub = StubDynamo(items=[
            _item('live', digest, expires_at=_offset_iso(1)),
            _item('stale', stale, expires_at=_offset_iso(-1)),
            ])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) == 'live'
        assert tokenauth.key_active_in_registry(
            stale, table='t', dynamodb_client=stub) is None

    def test_row_without_expires_at_authorizes_until_require_expiry(self):
        """Verify absent expiry is a policy switch, not a silent default.

        Mutation: the `require_expiry` guard dropped, so a row carrying
            no expires_at authorizes even once the registry is closed.
        Oracle: the same row read twice, once per flag value; only the
            flag differs, so the guard is the sole cause of the change.
        """
        digest = hashlib.sha256(b'k').hexdigest()
        stub = StubDynamo(items=[_item('c1', digest)])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) == 'c1'
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub,
            require_expiry=True) is None

    def test_unparseable_expires_at_denies(self):
        """Verify a corrupt expires_at fails closed rather than open.

        Mutation: the ValueError arm returning the client_id, or falling
            through past the expiry block, so a garbage timestamp reads
            as no expiry at all and authorizes forever.
        Oracle: a row identical to an authorizing one but for the
            timestamp text, which alone must flip the result to None.
        """
        digest = hashlib.sha256(b'k').hexdigest()
        stub = StubDynamo(items=[_item('c1', digest, expires_at='not-a-date')])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is None

    def test_naive_expires_at_is_read_as_utc(self):
        """Verify a naive stored expiry is compared as UTC, not local.

        Mutation: dropping the `replace(tzinfo=utc)` line, which raises
            TypeError comparing naive to aware and takes the whole
            request path down rather than denying.
        Oracle: a naive stamp one hour ahead in UTC, which must
            authorize; a backfilled row is the realistic source.
        """
        digest = hashlib.sha256(b'k').hexdigest()
        stub = StubDynamo(items=[
            _item('c1', digest, expires_at=_offset_iso(1, tz=None))])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) == 'c1'

    def test_expiry_is_checked_after_the_active_flag(self):
        """Verify a revoked client stays denied whatever its expiry says.

        Mutation: the expiry block replacing the active check rather
            than following it, which revives every revoked client whose
            expires_at is still ahead.
        Oracle: a row that is revoked AND unexpired - the one
            combination that tells the two gates apart.
        """
        digest = hashlib.sha256(b'k').hexdigest()
        stub = StubDynamo(items=[
            _item('c1', digest, active=False, expires_at=_offset_iso(1))])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is None

    def test_non_string_expires_at_denies_and_names_its_type(
            self, tokenauth_warnings):
        """Verify an epoch-number expires_at fails closed with a true reason.

        Mutation: reading expires_at through .get('S', '') alone, which
            treats an N row as undated and authorizes it forever while
            require_expiry is off.
        Oracle: the same row minus expires_at authorizes, so the N
            attribute alone flips the result; the log names type N.
        """
        digest = hashlib.sha256(b'k').hexdigest()
        undated = _item('c1', digest)
        epoch_row = {**undated, 'expires_at': {'N': '4102444800'}}
        assert tokenauth.key_active_in_registry(
            digest, table='t',
            dynamodb_client=StubDynamo(items=[undated])) == 'c1'
        assert tokenauth.key_active_in_registry(
            digest, table='t',
            dynamodb_client=StubDynamo(items=[epoch_row])) is None
        [(level, message)] = tokenauth_warnings
        assert 'type N' in message
        assert 'carries no expires_at' not in message

    def test_expired_key_denial_logs_a_warning(self, tokenauth_warnings):
        """Verify a lapsed key's refusal reaches the server log.

        Mutation: the expired branch returning None with no log line.
        Oracle: a WARNING record naming client 'stale'.
        """
        digest = hashlib.sha256(b'stale').hexdigest()
        stub = StubDynamo(
            items=[_item('stale', digest, expires_at=_offset_iso(-1))])
        assert tokenauth.key_active_in_registry(
            digest, table='t', dynamodb_client=stub) is None
        [(level, message)] = tokenauth_warnings
        assert level == 'WARNING'
        assert "'stale' expired at" in message

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


class TestMintKeyExpiry:
    """Tests for mint_key's expires_at option."""

    def test_ttl_days_lands_exactly_that_many_days_ahead(self):
        """Verify expires_at is created_at plus the requested days.

        Mutation: timedelta(hours=ttl_days) in place of days, or the
            offset added to a fixed epoch rather than to created_at.
        Oracle: the item's own created_at differenced against its
            expires_at, hand-computed as exactly 90 days.
        """
        stub = StubDynamo()
        tokenauth.mint_key('c1', table='t', ttl_days=90, dynamodb_client=stub)
        item = stub.put_calls[0]['Item']
        created = datetime.datetime.fromisoformat(item['created_at']['S'])
        expires = datetime.datetime.fromisoformat(item['expires_at']['S'])
        assert expires - created == datetime.timedelta(days=90)

    def test_no_ttl_writes_no_expires_at_attribute(self):
        """Verify the default mint stays non-expiring for old callers.

        Mutation: defaulting ttl_days to DEFAULT_TTL_DAYS in the
            function rather than in the CLI, which silently expires
            every key an existing API caller mints.
        Oracle: the attribute's presence in the put_item payload, which
            is what a registry row is built from.
        """
        stub = StubDynamo()
        tokenauth.mint_key('c1', table='t', dynamodb_client=stub)
        assert 'expires_at' not in stub.put_calls[0]['Item']

    @pytest.mark.parametrize('ttl', [0, -1])
    def test_non_positive_ttl_raises_before_writing(self, ttl):
        """Verify a dead-on-arrival lifetime is refused, not minted.

        Mutation: the `ttl_days <= 0` guard weakened to `< 0`, which
            lets 0 through and stores a key expired at the instant it
            prints - unrecoverable, since the raw key shows once.
        Oracle: no put_item call at all, which proves the guard runs
            before the write rather than after it.
        """
        stub = StubDynamo()
        with pytest.raises(ValueError):
            tokenauth.mint_key('c1', table='t', ttl_days=ttl,
                               dynamodb_client=stub)
        assert stub.put_calls == []


class TestRenewKey:
    """Tests for renew_key."""

    def test_renew_writes_expiry_from_now_and_touches_nothing_else(self):
        """Verify renew moves expires_at alone, measured from now.

        Mutation: the UpdateExpression also setting active or
            key_sha256, which would revive a revoked client or destroy a
            live credential during routine maintenance.
        Oracle: the UpdateExpression string and its value map, both
            hand-compared against the one attribute renew may touch.
        """
        pytest.importorskip('botocore')
        stub = StubDynamo()
        before = datetime.datetime.now(datetime.timezone.utc)
        returned = tokenauth.renew_key('c1', table='t', ttl_days=30,
                                       dynamodb_client=stub)
        call = stub.update_calls[0]
        assert call['UpdateExpression'] == 'SET expires_at = :e'
        assert set(call['ExpressionAttributeValues']) == {':e'}
        assert call['ExpressionAttributeValues'][':e']['S'] == returned
        expires = datetime.datetime.fromisoformat(returned)
        assert datetime.timedelta(days=30) <= expires - before <= (
            datetime.timedelta(days=30, seconds=60))

    def test_renew_does_not_stack_onto_an_existing_expiry(self):
        """Verify the new expiry runs from now, never from the old one.

        Mutation: computing the new expiry by adding ttl_days to the
            stored expires_at, so repeated renewals push a key years out
            and the 90-day ceiling stops bounding anything.
        Oracle: two renewals of the same client, whose returned expiries
            must differ by the wall-clock gap between them and not by a
            second ttl_days.
        """
        pytest.importorskip('botocore')
        stub = StubDynamo()
        first = tokenauth.renew_key('c1', table='t', ttl_days=30,
                                    dynamodb_client=stub)
        second = tokenauth.renew_key('c1', table='t', ttl_days=30,
                                     dynamodb_client=stub)
        gap = (datetime.datetime.fromisoformat(second)
               - datetime.datetime.fromisoformat(first))
        assert gap < datetime.timedelta(seconds=60)

    def test_missing_client_raises(self):
        """Verify renewing an unknown client raises ClientNotFoundError.

        Mutation: the ConditionExpression dropped, which would CREATE a
            bare row carrying an expires_at and no key_sha256 - a
            registry entry that authorizes nobody and hides a typo.
        Oracle: the botocore ConditionalCheckFailed error mapped to the
            module's own exception type.
        """
        pytest.importorskip('botocore')
        stub = StubDynamo(update_error=_conditional_error())
        with pytest.raises(tokenauth.ClientNotFoundError):
            tokenauth.renew_key('c1', table='t', dynamodb_client=stub)


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

    def test_expires_at_reaches_the_record(self):
        """Verify a row's expiry survives into the ClientRecord.

        Mutation: the expires_at field dropped from the ClientRecord
            construction, which defaults it to '' and makes every
            expiring key read as non-expiring in every listing.
        Oracle: a hand-set stamp on the item, compared literally.
        """
        stub = StubDynamo(items=[
            _item('c1', 'h1', expires_at='2026-06-01T00:00:00+00:00')])
        rows = tokenauth.list_clients(table='t', dynamodb_client=stub)
        assert rows[0].expires_at == '2026-06-01T00:00:00+00:00'

    def test_row_without_expiry_reports_empty_not_missing(self):
        """Verify a legacy row still builds a well-formed record.

        Mutation: reading expires_at without a default, which raises
            KeyError and takes down a listing over any pre-expiry row.
        Oracle: the field's value on a row that carries none.
        """
        stub = StubDynamo(items=[_item('c1', 'h1')])
        assert tokenauth.list_clients(
            table='t', dynamodb_client=stub)[0].expires_at == ''

    def test_epoch_expiry_lists_as_unreadable(self, capsys, monkeypatch):
        """Verify the CLI listing flags an N-typed expires_at it cannot read.

        Mutation: list_clients reading expires_at through .get('S', ''),
            which lists a row key_active_in_registry denies as 'never'.
        Oracle: the stored epoch text followed by the CLI's UNREADABLE
            marker, for a row whose only expiry is {'N': ...}.
        """
        row = {**_item('c1', 'h1'), 'expires_at': {'N': '4102444800'}}
        stub = StubDynamo(items=[row])
        monkeypatch.setattr(tokenauth, '_dynamodb_client', lambda *a: stub)
        assert tokenauth.run_cli(['--table', 't', 'list']) == 0
        out = capsys.readouterr().out
        assert '4102444800 UNREADABLE' in out
        assert 'never' not in out


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

    def test_add_defaults_to_the_ninety_day_ttl(self, capsys, monkeypatch):
        """Verify the CLI mints expiring keys where the API does not.

        Mutation: the --ttl-days default dropped to None, which returns
            the CLI to minting never-expiring keys and leaves the
            registry uncloseable while every command still reads right.
        Oracle: the ttl_days keyword mint_key is actually handed,
            captured by a spy, against DEFAULT_TTL_DAYS.
        """
        seen = {}
        monkeypatch.setattr(tokenauth, 'mint_key',
                            lambda *a, **k: seen.update(k) or 'rawkey')
        assert tokenauth.run_cli(['--table', 't', 'add', 'c1']) == 0
        assert seen['ttl_days'] == tokenauth.DEFAULT_TTL_DAYS
        assert 'never' not in capsys.readouterr().out

    def test_no_expiry_overrides_the_ttl(self, monkeypatch):
        """Verify --no-expiry wins over a --ttl-days on the same line.

        Mutation: the flags read in the other order, so --no-expiry is
            ignored whenever --ttl-days is also given and the operator's
            explicit never-expire request silently expires.
        Oracle: both flags passed together; ttl_days must arrive None.
        """
        seen = {}
        monkeypatch.setattr(tokenauth, 'mint_key',
                            lambda *a, **k: seen.update(k) or 'rawkey')
        tokenauth.run_cli(['--table', 't', 'add', 'c1',
                           '--ttl-days', '30', '--no-expiry'])
        assert seen['ttl_days'] is None

    def test_renew_missing_returns_1(self, monkeypatch):
        """Verify renew on an unknown client returns exit code 1.

        Mutation: the ClientNotFoundError arm omitted from the renew
            branch, so the traceback escapes and a script reading the
            exit code sees a crash rather than a handled refusal.
        Oracle: the exit code alone, against the 1 the other refusal
            branches already return.
        """
        def _boom(*a, **k):
            raise tokenauth.ClientNotFoundError('c1')
        monkeypatch.setattr(tokenauth, 'renew_key', _boom)
        assert tokenauth.run_cli(['--table', 't', 'renew', 'c1']) == 1

    def test_list_flags_an_expired_row_and_spares_a_live_one(
            self, capsys, monkeypatch):
        """Verify the EXPIRED marker parses rather than compares text.

        Mutation: comparing expires_at against an ISO string of now, as
            text. A 'Z'-suffixed future stamp sorts below a '+00:00'
            now, so a live key is labelled EXPIRED and an operator
            re-mints a working credential.
        Oracle: two rows an hour either side of now, the future one
            carrying the 'Z' spelling that breaks the text comparison.
        """
        monkeypatch.setattr(tokenauth, 'list_clients', lambda *a, **k: [
            tokenauth.ClientRecord('live', 'active', '2026-01-01',
                                   _offset_iso(1, suffix='Z')),
            tokenauth.ClientRecord('stale', 'active', '2026-01-01',
                                   _offset_iso(-1)),
            ])
        assert tokenauth.run_cli(['--table', 't', 'list']) == 0
        live, stale = [line for line in capsys.readouterr().out.splitlines()
                       if line.strip()]
        assert 'EXPIRED' not in live
        assert 'EXPIRED' in stale
