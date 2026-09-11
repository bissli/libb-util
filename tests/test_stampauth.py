"""Tests for the stampauth module.

Every stamp these tests verify is built HERE, from the contract in the
module docstring, and never by calling the module's own code. A verifier
checked against its own signing helper proves only self-agreement, and
the signing side of this contract lives in another repository.
"""

import base64
import hashlib
import hmac
import json
import time

import pytest

from libb import stampauth

CURRENT = 'c' * 40
PREVIOUS = 'p' * 40
GATEWAY = 'example-gw'


def _b64url(raw):
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _payload(**overrides):
    issued_at = int(time.time())
    payload = {
        'sub': 'user-sub',
        'cid': 'client-id',
        'grp': ['analysts'],
        'gw': GATEWAY,
        'iat': issued_at,
        'exp': issued_at + 60,
        }
    payload.update(overrides)
    return payload


def _stamp(payload=None, key=CURRENT, sign_decoded=False, pad=False):
    """Build a stamp the way the contract describes, by hand.

    sign_decoded signs the DECODED payload bytes instead of the segment
    text, which is the one mutation that breaks every deployed verifier
    at once while every round-trip test still passes.
    """
    payload = _payload() if payload is None else payload
    encoded = _b64url(
        json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8'))
    covered = _b64url_to_bytes(encoded) if sign_decoded else encoded.encode('ascii')
    signature = hmac.new(key.encode('utf-8'), covered, hashlib.sha256).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode('ascii')
    if not pad:
        signature_b64 = signature_b64.rstrip('=')
    return f'{stampauth.STAMP_VERSION}.{encoded}.{signature_b64}'


def _b64url_to_bytes(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class StubSecrets:
    """In-memory Secrets Manager client counting its reads."""

    def __init__(self, secret_string):
        self.secret_string = secret_string
        self.calls = 0

    def get_secret_value(self, SecretId):  # noqa: N803
        self.calls += 1
        return {'SecretString': self.secret_string}


@pytest.fixture(autouse=True)
def _clear_key_cache():
    stampauth._signing_key_cache.clear()
    yield
    stampauth._signing_key_cache.clear()


def test_a_contract_stamp_verifies():
    """Verify a stamp built from the contract alone is accepted.

    Mutation: any divergence from the contract in the parsing order -
        splitting on a different separator, expecting a padded
        signature, reading the payload before checking the HMAC.
    Oracle: a stamp assembled in this file from the module docstring's
        contract block, signed with a key this test chose.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(), [CURRENT], gateway=GATEWAY)

    assert reason == ''
    assert payload['sub'] == 'user-sub'
    assert payload['grp'] == ['analysts']


def test_the_hmac_must_cover_the_segment_text_not_the_decoded_bytes():
    """Verify a stamp signed over the decoded payload is refused.

    Mutation: hashing `_b64url_to_bytes(encoded)` instead of
        `encoded.encode('ascii')`. Both are one line apart, both make a
        sign-then-verify round trip pass, and the two disagree only
        against a signer that read the contract the other way - which
        is every real caller. This is the divergence that breaks each
        backend separately after deploy.
    Oracle: the same payload signed over its decoded bytes, which the
        contract does not describe, must fail.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(sign_decoded=True), [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == 'stamp signature does not verify'


def test_a_stamp_signed_with_the_previous_key_still_verifies():
    """Verify both halves of a two-secret rotation are accepted.

    Mutation: checking `keys[0]` alone, or breaking out of the key loop
        before the second entry. Every stamp minted before a rotation
        is then refused for the length of the signer's own key cache,
        which reads as a fleet-wide forgery alarm.
    Oracle: a stamp signed with PREVIOUS against a key list whose first
        entry is CURRENT.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(key=PREVIOUS), [CURRENT, PREVIOUS], gateway=GATEWAY)

    assert reason == ''
    assert payload['sub'] == 'user-sub'


def test_a_stamp_signed_with_an_unlisted_key_is_refused():
    """Verify a key absent from the list does not verify.

    Mutation: comparing with `==` on a truncated digest, or returning
        the payload before the HMAC result is consulted.
    Oracle: a stamp signed with PREVIOUS against CURRENT alone.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(key=PREVIOUS), [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == 'stamp signature does not verify'


def test_a_stamp_naming_another_gateway_is_refused():
    """Verify `gw` is checked, which is the whole anti-replay binding.

    Mutation: dropping the `gw` comparison. The stamp still verifies on
        its HMAC, so every other test here passes, and a stamp minted
        at one gateway replays at any other sharing the key - which is
        the reason the field exists.
    Oracle: a correctly signed stamp whose `gw` names a different
        gateway than the verifier was configured with.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(_payload(gw='other-gw')), [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == 'stamp names another gateway'


def test_the_expiry_boundary_refuses_a_stamp_expiring_exactly_now():
    """Verify `exp` equal to the clock is expired, not live.

    Mutation: `<` in place of `<=` on the expiry comparison. Only a
        stamp landing on the exact second tells the two apart, so a
        test using a comfortably live or comfortably dead stamp cannot.
    Oracle: a fixed clock compared against `exp` at that instant and
        one second later, asserted as a pair.
    """
    frozen = 1_800_000_000.0

    expired, reason = stampauth.verify_stamp(
        _stamp(_payload(exp=int(frozen))), [CURRENT],
        gateway=GATEWAY, now=frozen)
    live, live_reason = stampauth.verify_stamp(
        _stamp(_payload(exp=int(frozen) + 1)), [CURRENT],
        gateway=GATEWAY, now=frozen)

    assert expired is None
    assert reason == 'stamp expired'
    assert live_reason == ''
    assert live['exp'] == int(frozen) + 1


def test_a_non_finite_exp_is_refused():
    """Verify a nan or an inf expiry cannot mint an immortal stamp.

    Mutation: dropping the isfinite guard. `float('nan')` survives the
        numeric type check and compares False against every clock, so
        the stamp never expires; `inf` expires in no finite time.
    Oracle: a signed stamp whose `exp` is each of the two JSON literals
        Python's json module emits for them.
    """
    for literal in ('NaN', 'Infinity'):
        encoded = _b64url(
            ('{"cid":"client-id","exp":' + literal + ',"grp":["analysts"],'
             f'"gw":"{GATEWAY}","iat":1,"sub":"user-sub"}}').encode('utf-8'))
        signature = hmac.new(
            CURRENT.encode('utf-8'), encoded.encode('ascii'), hashlib.sha256).digest()
        stamp = f'{stampauth.STAMP_VERSION}.{encoded}.{_b64url(signature)}'

        payload, reason = stampauth.verify_stamp(
            stamp, [CURRENT], gateway=GATEWAY)

        assert payload is None, literal
        assert reason == 'malformed: exp is not a finite number'


def test_a_boolean_field_is_refused():
    """Verify `true` cannot stand in for a number or a string.

    Mutation: dropping the bool guard from the type loop.
        `isinstance(True, int)` holds, so `"exp": true` passes a
        numeric check and then compares as 1 against the clock -
        expired rather than crashing, which hides it.
    Oracle: a signed stamp whose `exp` is JSON `true`.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(_payload(exp=True)), [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == 'malformed: exp has the wrong type'


@pytest.mark.parametrize('field', ['sub', 'cid', 'grp', 'gw', 'iat', 'exp'])
def test_every_contract_field_is_required(field):
    """Verify each of the six contract keys must be present.

    Mutation: reading a field with `.get(field)` and a default rather
        than demanding it. A payload with no `sub` then attributes the
        call to the empty string, which reads in a log as a real user
        who happens to have no id.
    Oracle: one signed stamp per field, that field deleted.
    """
    payload = _payload()
    del payload[field]

    verified, reason = stampauth.verify_stamp(
        _stamp(payload), [CURRENT], gateway=GATEWAY)

    assert verified is None
    assert reason == f'malformed: payload has no {field}'


def test_a_string_group_claim_is_refused():
    """Verify `grp` must be a list, not a string that contains a name.

    Mutation: dropping `grp` from the type map. A membership test
        against a string is a SUBSTRING test, so a caller downstream
        checking `'analysts' in payload['grp']` passes on the value
        'non-analysts'.
    Oracle: a signed stamp whose `grp` is the string 'non-analysts'.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(_payload(grp='non-analysts')), [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == 'malformed: grp has the wrong type'


def test_an_unknown_extra_field_is_accepted():
    """Verify an added contract field does not refuse every call.

    Mutation: asserting the payload's key set equals the six exactly.
        The signing side and these backends deploy separately, so a
        strict set turns one added field at the gateway into a
        fail-closed outage on all of them at once.
    Oracle: a signed stamp carrying a seventh key, which must verify
        and must not appear as a failure.
    """
    payload, reason = stampauth.verify_stamp(
        _stamp(_payload(extra='added later')), [CURRENT], gateway=GATEWAY)

    assert reason == ''
    assert payload['extra'] == 'added later'


def test_a_padded_signature_is_refused():
    """Verify padded base64url does not verify.

    Mutation: dropping the padding check. A padded signature segment
        decodes to the identical bytes, so two distinct header values
        would carry one identity and a log could not tell them apart.
    Oracle: the same stamp with its signature padding left on.
    """
    padded = _stamp(pad=True)

    payload, reason = stampauth.verify_stamp(padded, [CURRENT], gateway=GATEWAY)

    assert '=' in padded
    assert payload is None
    assert reason == 'malformed: base64url is padded'


@pytest.mark.parametrize(('stamp', 'expected'), [
    ('', 'no stamp presented'),
    ('t1.only-two', 'malformed: not three segments'),
    ('t1.a.b.c', 'malformed: not three segments'),
    ('t2.abc.def', "unknown stamp version 't2'"),
    ('.abc.def', "unknown stamp version ''"),
])
def test_a_malformed_stamp_names_its_own_fault(stamp, expected):
    """Verify the shape checks run before any crypto and each is distinct.

    Mutation: collapsing the shape checks into one reason, or letting a
        two-segment value reach the unpacking - which raises ValueError
        and reaches the caller as a 500 where a refusal belongs.
    Oracle: one probe per shape, each asserting its own reason text.
    """
    payload, reason = stampauth.verify_stamp(stamp, [CURRENT], gateway=GATEWAY)

    assert payload is None
    assert reason == expected


def test_an_empty_key_list_refuses_rather_than_accepting_everything():
    """Verify a missing key denies instead of skipping the signature check.

    Mutation: treating an empty key list as nothing to check and
        returning the payload. Every stamp, forged included, then
        verifies on a backend whose secret failed to load - the one
        failure here that does not look like an outage.
    Oracle: a correctly signed stamp against an empty key list.
    """
    payload, reason = stampauth.verify_stamp(_stamp(), [], gateway=GATEWAY)

    assert payload is None
    assert reason == 'no signing key configured'


def test_an_empty_gateway_name_refuses():
    """Verify an unset gateway name denies rather than skipping `gw`.

    Mutation: comparing `payload['gw'] != gateway` with no guard above
        it. An empty configured name then matches only a stamp whose
        `gw` is empty, which looks like it denies - but the guard is
        what makes the fault legible instead of reading as a signer
        problem.
    Oracle: a correctly signed stamp against an empty gateway name.
    """
    payload, reason = stampauth.verify_stamp(_stamp(), [CURRENT], gateway='')

    assert payload is None
    assert reason == 'no gateway name configured to bind the stamp to'


def test_the_rotation_shape_returns_current_before_previous():
    """Verify both keys are read and current is tried first.

    Mutation: returning `previous` first, or dropping it. Order decides
        which key signs a stamp on the signing side and which verifies
        first here; dropping `previous` refuses every pre-rotation
        stamp.
    Oracle: a stored object whose two values are distinguishable, read
        back as an ordered tuple.
    """
    stub = StubSecrets(json.dumps({'current': CURRENT, 'previous': PREVIOUS}))

    assert stampauth.signing_keys('s', secrets_client=stub) == (CURRENT, PREVIOUS)


def test_a_bare_string_secret_is_accepted_and_stripped():
    """Verify a hand-created secret works and its newline is dropped.

    Mutation: dropping `.strip()`. `openssl rand -base64 32` writes a
        trailing newline, which would be HMAC'd as part of the key, so
        the backend and the signer derive different keys from one
        stored secret and every stamp is refused as forged.
    Oracle: the same key stored with a trailing newline, compared
        against the bare key.
    """
    stub = StubSecrets(CURRENT + '\n')

    assert stampauth.signing_keys('s', secrets_client=stub) == (CURRENT,)


@pytest.mark.parametrize('stored', [
    '{"current": null}',
    '{"current": 12345678901234567890123456789012345}',
    '{"current": ["' + CURRENT + '"]}',
    '12345678901234567890123456789012345',
    'true',
])
def test_a_non_string_key_is_refused_rather_than_coerced(stored):
    """Verify a key of the wrong type denies instead of being str()'d.

    Mutation: `str(parsed.get('current'))`. A JSON null then signs with
        the four-byte 'None' and a number with its own digits - keys a
        stranger guesses against a published stamp format, and the
        stamp is the whole of attribution.
    Oracle: five stored shapes a rotation or a hand edit can really
        write, each asserted to yield no key at all.
    """
    stub = StubSecrets(stored)

    assert stampauth.signing_keys('s', secrets_client=stub) == ()


def test_a_digit_string_with_a_leading_zero_is_read_as_a_key():
    """Verify the JSON-first parse does not swallow a valid key.

    Mutation: parsing a bare secret as a string without trying JSON
        first, or the reverse. A leading zero makes an all-digit secret
        invalid JSON, so it arrives as a string and must be accepted,
        while the same digits without the zero parse as a number and
        must be refused - the pair is what pins the order.
    Oracle: the two secrets side by side, differing in one leading
        character.
    """
    usable = '0' + '1' * 39
    unusable = '1' * 40

    assert stampauth.signing_keys('s', secrets_client=StubSecrets(usable)) == (usable,)
    stampauth._signing_key_cache.clear()
    assert stampauth.signing_keys('s', secrets_client=StubSecrets(unusable)) == ()


def test_the_key_length_floor_is_checked_at_its_boundary():
    """Verify a key one character short is refused and the floor passes.

    Mutation: `>` in place of `>=` on the length comparison, or a
        different constant. Only the pair either side of 32 separates
        them, and a truncated rotation writes exactly this shape.
    Oracle: keys of length 31 and 32 asserted as a pair, against the
        published digest size rather than the module's own constant.
    """
    assert stampauth.MIN_SIGNING_KEY_LENGTH == hashlib.sha256().digest_size

    short = 'k' * 31
    exact = 'k' * 32

    assert stampauth.signing_keys('s', secrets_client=StubSecrets(short)) == ()
    stampauth._signing_key_cache.clear()
    assert stampauth.signing_keys('s', secrets_client=StubSecrets(exact)) == (exact,)


def test_an_accepted_read_is_cached_and_a_refused_one_is_not():
    """Verify the TTL cache holds a key but never holds a refusal.

    Mutation: caching the result unconditionally. A corrected secret
        then stays refused for the whole TTL on every warm process,
        long after an operator fixed it - and the denial names a fault
        that no longer exists.
    Oracle: a stub counting its reads, asserted after two calls on a
        good secret and two on a bad one.
    """
    good = StubSecrets(json.dumps({'current': CURRENT}))
    stampauth.signing_keys('good', secrets_client=good)
    stampauth.signing_keys('good', secrets_client=good)

    bad = StubSecrets('{"current": null}')
    stampauth.signing_keys('bad', secrets_client=bad)
    stampauth.signing_keys('bad', secrets_client=bad)

    assert good.calls == 1
    assert bad.calls == 2


def test_a_zero_ttl_reads_every_time():
    """Verify ttl_seconds=0 disables reuse rather than caching forever.

    Mutation: dropping the freshness comparison and reusing whatever
        is cached (`if cached:`). A zero TTL is how an operator turns
        caching off to make a rotation land at once, and that reading
        serves the retired key for the life of the process instead.
    Oracle: a counting stub called twice with ttl_seconds=0.

    Note: `>=` for `>` on that same comparison is NOT caught here and
    is not a gap. The two differ only when `read_at` equals the clock
    exactly, which no reachable input arranges.
    """
    stub = StubSecrets(json.dumps({'current': CURRENT}))

    stampauth.signing_keys('s', ttl_seconds=0, secrets_client=stub)
    stampauth.signing_keys('s', ttl_seconds=0, secrets_client=stub)

    assert stub.calls == 2


def test_an_empty_secret_id_reads_nothing():
    """Verify an unconfigured secret id makes no AWS call.

    Mutation: dropping the guard, which sends an empty SecretId to
        Secrets Manager on every request and turns a missing setting
        into a per-call API error rather than a clear denial.
    Oracle: a counting stub asserted untouched.
    """
    stub = StubSecrets(CURRENT)

    assert stampauth.signing_keys('', secrets_client=stub) == ()
    assert stub.calls == 0


class Recorder:
    """Minimal ASGI app recording the scope it was called with."""

    def __init__(self):
        self.scopes = []

    async def __call__(self, scope, receive, send):
        self.scopes.append(scope)
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b'{}'})


def _drive(middleware, scope):
    """Run one request through a raw-ASGI middleware, returning the status."""
    import asyncio

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    asyncio.run(middleware(scope, receive, send))
    return sent[0]['status']


def _scope(path='/mcp', stamp=None, header=b'x-identity-stamp'):
    headers = [(b'host', b'example')]
    if stamp is not None:
        headers.append((header, stamp.encode('latin-1')))
    return {'type': 'http', 'path': path, 'headers': headers}


def _middleware(app, required=False, gateway=GATEWAY, keys=(CURRENT,)):
    return stampauth.StampIdentityMiddleware(
        app,
        protected_prefixes=('/mcp',),
        header='X-Identity-Stamp',
        keys=lambda: keys,
        gateway=gateway,
        required=required)


def test_an_invalid_stamp_is_refused_even_when_not_required():
    """Verify permissive mode never downgrades a forgery to anonymous.

    Mutation: reading `required` as the switch for a BAD stamp as well
        as an absent one - the reading a per-server rollout flag
        invites. A forger then sends any garbage, is served as
        unattributed, and the gate that was supposed to reject it
        instead hides it. This is the whole reason absence and
        invalidity are separate branches.
    Oracle: a stamp signed with a key the verifier does not hold,
        against a middleware with required=False, asserted 403 and the
        wrapped app never reached.
    """
    app = Recorder()

    status = _drive(_middleware(app, required=False),
                    _scope(stamp=_stamp(key=PREVIOUS)))

    assert status == 403
    assert app.scopes == []


def test_an_absent_stamp_passes_when_not_required_and_refuses_when_required():
    """Verify `required` governs absence, in both positions.

    Mutation: inverting the flag, or ignoring it. Permissive is what
        keeps a private path serving while its callers gain no stamp,
        and the flip is the only thing that later closes that path -
        a flag wired one way round does one of those and not the other.
    Oracle: the same stampless request through both settings, asserted
        as a pair.
    """
    permissive, strict = Recorder(), Recorder()

    assert _drive(_middleware(permissive, required=False), _scope()) == 200
    assert _drive(_middleware(strict, required=True), _scope()) == 403
    assert len(permissive.scopes) == 1
    assert strict.scopes == []


def test_the_verified_payload_reaches_the_wrapped_app():
    """Verify the attribution a handler reads is published on the scope.

    Mutation: writing the raw header, or nothing, to
        `scope['state']['identity_stamp']`. A handler logging that key
        then records the caller's own unverified text as identity,
        which is the forgery this module exists to stop.
    Oracle: the decoded `sub` read back off the scope the wrapped app
        received.
    """
    app = Recorder()

    status = _drive(_middleware(app), _scope(stamp=_stamp()))

    assert status == 200
    assert app.scopes[0]['state']['identity_stamp']['sub'] == 'user-sub'


def test_an_unprotected_path_is_never_gated():
    """Verify a path outside the prefixes passes with no stamp read.

    Mutation: dropping the prefix test. A health check then needs a
        stamp, so the orchestrator reads every task as unhealthy and
        cycles the whole service - an outage caused by the gate rather
        than by anything it caught.
    Oracle: a stampless /health request through a required=True
        middleware, asserted 200.
    """
    app = Recorder()

    assert _drive(_middleware(app, required=True), _scope(path='/health')) == 200
    assert len(app.scopes) == 1


def test_a_websocket_scope_under_a_gated_prefix_passes_through():
    """Verify a non-http scope is not gated even with required=True.

    Mutation: dropping the scope-type test. A websocket handshake
        carries no stamp header, so it would then be refused with an
        http response frame sent down a websocket - a failure that
        names nothing at either end. Only a non-http scope on a
        PROTECTED path reaches that branch, so the prefix test alone
        does not cover it.
    Oracle: a websocket scope at /mcp through a required=True
        middleware, asserted to reach the wrapped app.
    """
    app = Recorder()
    scope = {'type': 'websocket', 'path': '/mcp', 'headers': []}

    _drive(_middleware(app, required=True), scope)

    assert app.scopes == [scope]


def test_a_key_lookup_that_raises_denies_rather_than_500s():
    """Verify a Secrets Manager outage refuses instead of propagating.

    Mutation: letting the exception escape. It reaches the caller as a
        500 and, on a server configured to return tracebacks, as the
        secret id and the call stack; it also reads as a server fault
        rather than as the fail-closed refusal it is.
    Oracle: a keys callable that raises, asserted 403 with the wrapped
        app never reached.
    """
    app = Recorder()

    def explode():
        raise RuntimeError('secrets manager unreachable')

    middleware = stampauth.StampIdentityMiddleware(
        app, protected_prefixes=('/mcp',), header='X-Identity-Stamp',
        keys=explode, gateway=GATEWAY, required=False)

    assert _drive(middleware, _scope(stamp=_stamp())) == 403
    assert app.scopes == []


def test_the_header_name_is_matched_case_insensitively():
    """Verify a differently cased header still carries the stamp.

    Mutation: comparing the configured name without lowering it. HTTP
        header names are case-insensitive and h2 lowercases them all,
        so a name configured with capitals would match on HTTP/1
        and silently stop matching behind an h2 proxy - every call
        served as unattributed with nothing logged as wrong.
    Oracle: the same stamp sent under an upper-cased header name.
    """
    app = Recorder()

    status = _drive(_middleware(app),
                    _scope(stamp=_stamp(), header=b'X-IDENTITY-STAMP'))

    assert status == 200
    assert app.scopes[0]['state']['identity_stamp']['sub'] == 'user-sub'


@pytest.mark.parametrize('junk', ['!!!!', '!!!!!!!!', '\n\n\n\n', '@@@@'])
def test_stray_characters_in_the_signature_segment_are_refused(junk):
    """Verify one identity cannot have many header values.

    Mutation: `urlsafe_b64decode(...)`, or `b64decode` without
        `validate=True`. Both DISCARD non-alphabet characters, so junk
        appended in multiples of four decodes to the same octets and
        `t1.<p>.<sig>` and `t1.<p>.<sig>!!!!` both verify. Three
        distinct header values carried one identity before the fix. A
        single stray character fails either way, because it shifts the
        computed padding - so only a multiple of four exposes it, which
        is why this is parametrized rather than a lone probe.
    Oracle: the canonical stamp accepted, and the same stamp with each
        junk run appended refused, asserted as a pair. A '.' run is
        excluded on purpose: it is the segment separator, so it trips
        the three-segment guard before the decoder ever sees it.
    """
    canonical = _stamp()

    accepted, _ = stampauth.verify_stamp(canonical, [CURRENT], gateway=GATEWAY)
    payload, reason = stampauth.verify_stamp(
        canonical + junk, [CURRENT], gateway=GATEWAY)

    assert accepted is not None
    assert payload is None
    assert reason == 'malformed: payload or signature segment is not base64url'


def test_a_broken_current_key_denies_rather_than_falling_back():
    """Verify a half-written rotation cannot keep verifying on `previous`.

    Mutation: filtering the two candidates independently, so an
        unusable `current` beside a valid `previous` returns
        `(previous,)`. The SIGNING side denies outright on a bad
        `current`, so the fallback leaves the two ends disagreeing about
        whether the secret is broken - the signer refuses every call
        while a verifier still honors the retired key.
    Oracle: three stored shapes - a broken `current` with a good
        `previous`, a good `current` with a broken `previous`, and both
        good - asserted as (), one key, and two keys.
    """
    broken_current = StubSecrets(json.dumps(
        {'current': None, 'previous': PREVIOUS}))
    broken_previous = StubSecrets(json.dumps(
        {'current': CURRENT, 'previous': 'short'}))
    both = StubSecrets(json.dumps({'current': CURRENT, 'previous': PREVIOUS}))

    assert stampauth.signing_keys('a', secrets_client=broken_current) == ()
    assert stampauth.signing_keys('b', secrets_client=broken_previous) == (CURRENT,)
    assert stampauth.signing_keys('c', secrets_client=both) == (CURRENT, PREVIOUS)
