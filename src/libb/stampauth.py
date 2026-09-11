"""Stamp auth: verify a signed per-user identity stamp from a gateway.

An aggregating gateway authenticates itself to every backend with one
shared credential, so a backend cannot tell one end user from another. A
request interceptor at the gateway is the only source of that
attribution: it verifies the caller's own token and stamps an
HMAC-signed identity. This module is the upstream half - the check a
backend runs before it believes a name.

Layers, low to high:

- :func:`verify_stamp` - the pure check. No I/O and no AWS, written
  against the stamp contract rather than against any signing code.
- :func:`signing_keys` - read the shared secret from Secrets Manager and
  return the keys a stamp may be signed with, cached for a bounded time.
- :class:`StampIdentityMiddleware` - a raw-ASGI gate that runs
  :func:`verify_stamp` for chosen path prefixes and publishes the
  verified payload at ``scope['state']['identity_stamp']``.

The header name, the gateway name, the secret id and the key lookup are
all injected by the caller -- nothing is hardcoded -- so the same code
serves any deployment.

Notes
-----
- A name a caller can write is not an identity. A gateway strips
  client-supplied headers before the BACKEND but not before its own
  interceptor, so the interceptor overwrites rather than merges, and
  this module trusts the stamp alone. Any per-request identity arriving
  by another route is the caller's own claim about itself.
- An ABSENT stamp and an INVALID one are different events. A backend
  often also serves a private path where no stamp exists, so absence is
  what ``required`` governs; an unverifiable stamp is refused whatever
  ``required`` says. Downgrading a forgery to anonymous would let a
  forger choose to be unattributed, and reading it as identity is the
  hole this module closes.
- HMAC rather than an asymmetric signature suits a stamp whose two ends
  are owned by one operator, with the shared secret on a two-secret
  rotation.

The stamp contract
------------------
Header value ``t1.<payload>.<signature>``, both segments unpadded
base64url::

    signature = HMAC-SHA256(key, payload)   over the payload segment's
                                            ASCII TEXT, not its bytes
    payload   = {"cid", "exp", "grp", "gw", "iat", "sub"}

``gw`` is the gateway NAME, so a stamp minted for one gateway does not
replay at another sharing the key - which holds only because a verifier
checks it. ``exp`` is read from the stamp and never assumed. Across a
rotation the secret holds ``current`` and ``previous``: the signing side
uses ``current`` and a verifier accepts either.

The ``boto3`` dependency is optional and only :func:`signing_keys` needs
it: install ``libb-util[tokenauth]``.
"""
import hashlib
import hmac
import json
import logging
import math
import time
from base64 import b64decode
from collections.abc import Callable, Iterable, Sequence
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    'MIN_SIGNING_KEY_LENGTH',
    'STAMP_VERSION',
    'StampIdentityMiddleware',
    'signing_keys',
    'verify_stamp',
]

STAMP_VERSION = 't1'

MIN_SIGNING_KEY_LENGTH = 32

_PAYLOAD_TYPES: dict[str, type | tuple[type, ...]] = {
    'sub': str,
    'cid': str,
    'grp': list,
    'gw': str,
    'iat': (int, float),
    'exp': (int, float),
    }

_MISSING = object()

_signing_key_cache: dict[str, dict[str, Any]] = {}
_secrets_client: Any = None


def _b64url_to_bytes(value: str) -> bytes:
    """Decode unpadded base64url text to raw bytes, refusing stray characters.

    Parameters
    ----------
    value : str
        One unpadded base64url segment.

    Returns
    -------
    bytes
        The decoded octets.

    Raises
    ------
    binascii.Error
        A character outside the base64url alphabet appears in `value`.

    Notes
    -----
    - `validate=True` is the whole point, and `urlsafe_b64decode` cannot
      express it: it forwards to `b64decode` with the default
      `validate=False`, which silently DISCARDS every non-alphabet
      character. Junk appended to the signature segment in multiples of
      four then decodes to the same octets, so `t1.<p>.<sig>` and
      `t1.<p>.<sig>!!!!` both verify and one identity has unboundedly
      many header values. Measured before the fix.
    - That is malleability rather than forgery, since the key is still
      required. It still matters: any replay cache, dedupe or audit join
      keyed on the header TEXT is bypassable by padding the signature.
    """
    return b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def verify_stamp(
    stamp: str,
    keys: Sequence[str],
    *,
    gateway: str,
    now: float | None = None,
) -> tuple[dict | None, str]:
    """Verify a signed identity stamp and return its payload.

    Parameters
    ----------
    stamp : str
        The header value as presented, `t1.<payload>.<signature>`.
    keys : Sequence[str]
        Keys the stamp may be signed with, most current first. Every
        entry is tried, so a stamp minted either side of a rotation
        verifies.
    gateway : str
        Gateway NAME the stamp must name in `gw`. An empty value is a
        configuration fault and refuses every stamp, because `gw` is
        the whole of the anti-replay binding.
    now : float | None, optional
        Unix time to compare `exp` against. Defaults to `time.time()`.

    Returns
    -------
    tuple[dict | None, str]
        The payload and an empty string on success; None and a short
        reason naming the failed check otherwise.

    Notes
    -----
    - The signature is checked BEFORE the expiry and before `gw`, so a
      forger learns nothing from which check failed. Every caller-facing
      answer is the same refusal; the reason is for the log.
    - The six contract keys must be present and of the contract's type.
      An extra key is IGNORED rather than refused: the signing side and
      the backends deploy separately, so refusing an unknown key would
      turn one added field into a fleet-wide outage that fails closed.
    - Padding refuses. The contract is unpadded throughout and the
      signing side never emits it, so accepting a padded signature
      segment would let two distinct header values carry one identity.
    - `exp` is read from the stamp rather than recomputed from a
      configured lifetime. The signing side owns the lifetime and may
      change it without a verifier deploy.
    - A bool is refused for every field. `isinstance(True, int)` holds,
      so `"exp": true` would otherwise pass the numeric check and then
      compare as 1 against the clock.
    """
    if not gateway:
        return None, 'no gateway name configured to bind the stamp to'
    if not keys:
        return None, 'no signing key configured'
    if not stamp:
        return None, 'no stamp presented'
    if '=' in stamp:
        return None, 'malformed: base64url is padded'
    parts = stamp.split('.')
    if len(parts) != 3:
        return None, 'malformed: not three segments'
    version, encoded, signature_b64 = parts
    if version != STAMP_VERSION:
        return None, f'unknown stamp version {version!r}'
    try:
        signed = encoded.encode('ascii')
        presented = _b64url_to_bytes(signature_b64)
    except Exception:
        return None, 'malformed: payload or signature segment is not base64url'
    if not any(
        hmac.compare_digest(
            presented, hmac.new(key.encode('utf-8'), signed, hashlib.sha256).digest())
        for key in keys
    ):
        return None, 'stamp signature does not verify'
    try:
        payload = json.loads(_b64url_to_bytes(encoded))
    except Exception:
        return None, 'malformed: payload did not decode'
    if not isinstance(payload, dict):
        return None, 'malformed: payload is not a JSON object'
    for field, expected_type in _PAYLOAD_TYPES.items():
        value = payload.get(field, _MISSING)
        if value is _MISSING:
            return None, f'malformed: payload has no {field}'
        if isinstance(value, bool) or not isinstance(value, expected_type):
            return None, f'malformed: {field} has the wrong type'
    if payload['gw'] != gateway:
        return None, 'stamp names another gateway'
    expires_at = float(payload['exp'])
    # isfinite, not just numeric: a nan or an inf survives float() and
    # then compares False against any clock, so the stamp never expires.
    if not math.isfinite(expires_at):
        return None, 'malformed: exp is not a finite number'
    if expires_at <= (time.time() if now is None else now):
        return None, 'stamp expired'
    return payload, ''


def signing_keys(
    secret_id: str,
    *,
    ttl_seconds: int = 300,
    secrets_client: Any = None,
) -> tuple[str, ...]:
    """Read the stamp signing keys from Secrets Manager, cached per process.

    Parameters
    ----------
    secret_id : str
        Secret name or ARN holding the shared key.
    ttl_seconds : int, default 300
        How long a cached read may be reused. This is what lets a
        rotation reach a running process without a redeploy.
    secrets_client : Any, optional
        Injected boto3 Secrets Manager client. Built on first use when
        not given, so a process that never verifies a stamp never pays
        for one.

    Returns
    -------
    tuple[str, ...]
        `current`, then `previous` when that is usable too. An empty
        tuple when `current` is unusable, which denies every stamp -
        `previous` alone is never returned.

    Notes
    -----
    - Two stored shapes are accepted. A JSON object whose `current` is
      a STRING is what a two-secret rotation writes; a bare string is
      what a hand-created secret holds.
    - A non-string key is refused rather than coerced. `str()` on
      `{"current": null}` signs with the four-byte `'None'` and on a
      number with its digits, either of which a stranger guesses, and
      the stamp is the whole of attribution.
    - `MIN_SIGNING_KEY_LENGTH` matches the SHA-256 digest the stamp is
      HMAC'd with. It also catches a truncated or half-written
      rotation, which reads as a valid string.
    - A REJECTED read is not cached. Caching it held the refusal for
      the whole TTL after an operator had already corrected the secret.
    - A bare-string secret is stripped, because `openssl rand -base64
      32` writes a trailing newline that would otherwise count toward
      both the floor and the key.
    """
    global _secrets_client
    if not secret_id:
        return ()
    cached = _signing_key_cache.get(secret_id)
    if cached and cached['read_at'] + ttl_seconds > time.time():
        return cached['keys']
    if secrets_client is None:
        if _secrets_client is None:
            import boto3
            _secrets_client = boto3.client('secretsmanager')
        secrets_client = _secrets_client
    stored = secrets_client.get_secret_value(SecretId=secret_id)['SecretString']
    try:
        parsed = json.loads(stored)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        shape = 'json'
        candidates = (parsed.get('current'), parsed.get('previous'))
    elif parsed is None:
        shape = 'string'
        candidates = (stored.strip(), None)
    else:
        shape = type(parsed).__name__
        candidates = (None, None)
    # Notes:
    # - A broken `current` denies outright rather than falling back to
    #   `previous`. The signing side does the same, so a fallback here
    #   would leave the two ends disagreeing about whether the secret is
    #   broken: the signer refuses every call while a verifier keeps
    #   honoring the retired key, which is the half-written rotation
    #   surviving as a working credential.
    # - `previous` is filtered on the same rules and simply dropped when
    #   unusable, because a rotation that has not written it yet is the
    #   normal steady state.
    usable = [
        value if isinstance(value, str) and len(value) >= MIN_SIGNING_KEY_LENGTH
        else None
        for value in candidates]
    keys = tuple(value for value in usable if value is not None) if usable[0] else ()
    if not keys:
        current = candidates[0]
        logger.error(
            f'signing secret is {shape}, and its current key is '
            f'{type(current).__name__} of length '
            f'{len(current) if isinstance(current, str) else 0} '
            f'against a minimum of {MIN_SIGNING_KEY_LENGTH}')
        return ()
    _signing_key_cache[secret_id] = {'keys': keys, 'read_at': time.time()}
    logger.info(f'signing keys read, shape={shape}, accepted={len(keys)}')
    return keys


class StampIdentityMiddleware:
    """Raw ASGI middleware attributing a request to the stamped user.

    Requests under ``protected_prefixes`` are verified against the stamp
    contract and the authorized payload is published at
    ``scope['state']['identity_stamp']``, so a downstream handler
    attributes the call without re-reading the header::

        app.add_middleware(
            StampIdentityMiddleware,
            protected_prefixes=('/mcp',),
            header=STAMP_HEADER,
            keys=lambda: signing_keys(SECRET_ID),
            gateway=GATEWAY_NAME,
            required=False)

    Parameters
    ----------
    app : Any
        The wrapped ASGI application.
    protected_prefixes : Iterable[str]
        Path prefixes the stamp is read on.
    header : str
        Header carrying the stamp. Matched case-insensitively, and it
        must be the name the gateway's interceptor writes.
    keys : Callable[[], Sequence[str]]
        Returns the keys a stamp may be signed with. Called per gated
        request, so a rotation lands on whatever cadence the callable
        caches on, and a process that never serves a gated path never
        reads the secret.
    gateway : str
        Gateway NAME the stamp must name.
    required : bool, default False
        Whether a request with NO stamp is refused. False serves it as
        unattributed, which is what a private path needs while some
        callers do not reach the gateway; True refuses it.

    Notes
    -----
    - Only ``required`` governs ABSENCE. An unverifiable stamp is
      refused either way, so a forger cannot choose to be anonymous.
    - Runs AFTER the credential gate in the middleware stack, never
      instead of it. The stamp says which user; the credential says the
      caller may be here at all.
    - Only ``http`` scopes are gated, matching
      :class:`~libb.tokenauth.ApiTokenMiddleware`: a ``websocket``
      connection passes through, so do not place one under a protected
      prefix expecting a stamp to be read.
    - Verification is pure Python over a cached key, so it runs inline
      rather than on a worker thread. The key read behind ``keys`` is
      the only call that can block, and its own cache bounds how often.
    - The refusal names no failed check. A verifier that distinguished
      an expired stamp from a forged one would tell a forger which half
      to work on.
    """

    def __init__(
        self,
        app: Any,
        *,
        protected_prefixes: Iterable[str],
        header: str,
        keys: Callable[[], Sequence[str]],
        gateway: str,
        required: bool = False,
    ) -> None:
        """Wrap an ASGI app with the stamp check.
        """
        self.app = app
        self.protected_prefixes = tuple(protected_prefixes)
        self.header = header.lower()
        self._keys = keys
        self.gateway = gateway
        self.required = required

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """Attribute the request, refusing a stamp that does not verify.
        """
        if (scope.get('type') != 'http'
                or not scope.get('path', '').startswith(self.protected_prefixes)):
            await self.app(scope, receive, send)
            return
        presented = ''
        for key, value in scope.get('headers', []):
            if key.decode('latin-1').lower() == self.header:
                presented = value.decode('latin-1')
                break
        if not presented:
            if self.required:
                logger.warning('no stamp presented and one is required; denying')
                await _send_forbidden(send)
                return
            logger.debug('no stamp presented; serving unattributed')
            await self.app(scope, receive, send)
            return
        try:
            payload, reason = verify_stamp(
                presented, self._keys(), gateway=self.gateway)
        except Exception as exc:
            logger.warning(f'stamp verification raised; denying (fail closed): {exc}')
            await _send_forbidden(send)
            return
        if payload is None:
            logger.warning(f'stamp rejected: {reason}')
            await _send_forbidden(send)
            return
        scope.setdefault('state', {})['identity_stamp'] = payload
        await self.app(scope, receive, send)


async def _send_forbidden(send: Any) -> None:
    """Emit a raw-ASGI 403 JSON response naming no failed check.
    """
    body = b'{"detail":"Forbidden"}'
    await send({
        'type': 'http.response.start',
        'status': 403,
        'headers': [
            (b'content-type', b'application/json'),
            (b'content-length', str(len(body)).encode('latin-1')),
            ],
        })
    await send({'type': 'http.response.body', 'body': body})
