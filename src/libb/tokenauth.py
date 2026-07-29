"""Token-registry auth: per-client API keys backed by a DynamoDB table.

A small, framework-agnostic toolkit for gating machine endpoints (MCP /
API) on per-client keys. Keys are minted once, stored only as SHA-256
hashes, and looked up by a ``key_sha256`` global secondary index; a client
is allowed only while its item is ``active``. The table name, AWS region,
and boto3 client are all injected by the caller -- nothing is hardcoded --
so the same code serves any ``<name>`` registry table.

Layers, low to high:

- :func:`key_active_in_registry` -- the raw DynamoDB lookup (one GSI
  query). No caching: wrap it in a TTL cache and pass the wrapper as
  ``registry_check`` below to keep the lookup off a request hot path.
- :func:`verify_token` -- authorize a presented key: static break-glass
  token (constant time) then the registry, failing closed.
- :class:`ApiTokenMiddleware` -- a raw-ASGI gate that runs a
  ``(presented) -> str | None`` verifier (typically
  ``functools.partial(verify_token, ...)``) for chosen path prefixes.
- :func:`mint_key` / :func:`revoke_key` / :func:`list_clients` and the
  ``libb-tokenauth`` CLI (:func:`run_cli`) -- provisioning.

Both :func:`verify_token` and :class:`ApiTokenMiddleware` independently
fail closed; used together that is deliberate defense-in-depth.

The authorization layers return the *identity* they authorized -- a
client_id string, or None when denied -- rather than a bare bool, and
:class:`ApiTokenMiddleware` publishes it at ``scope['state']['client_id']``
so a downstream handler can log which human made the call. Returning an
identity keeps the truthiness contract of the old bool, so ``if
verify_token(...)`` still reads correctly.

A credential is read from the ``X-API-Key`` or ``Authorization: Bearer``
header only. A ``?key=`` query parameter is deliberately not accepted:
query strings are recorded verbatim by proxy and web-server access logs,
so that form turns every request into a credential disclosure.

Expected table shape::

    client_id   (S)  -- partition key
    client_name (S)  -- stored by mint_key; not returned by list_clients
    key_sha256  (S)  -- GSI 'key_sha256-index', projection ALL
    active      (BOOL)
    created_at  (S)  -- ISO-8601 UTC

The ``boto3`` dependency is optional: install ``libb-util[tokenauth]``.
"""
import datetime
import hashlib
import logging
import secrets
from collections.abc import Callable, Iterable
from typing import Any, Literal, NamedTuple

logger = logging.getLogger(__name__)

__all__ = [
    'KEY_SHA256_INDEX',
    'STATIC_TOKEN_CLIENT_ID',
    'UNKNOWN_CLIENT_ID',
    'ClientExistsError',
    'ClientNotFoundError',
    'ClientRecord',
    'hash_key',
    'key_active_in_registry',
    'verify_token',
    'mint_key',
    'revoke_key',
    'list_clients',
    'ApiTokenMiddleware',
]

KEY_SHA256_INDEX = 'key_sha256-index'

STATIC_TOKEN_CLIENT_ID = 'static-token'

UNKNOWN_CLIENT_ID = 'unknown'


def _as_client_id(result: Any) -> str | None:
    """Normalize an authorizer result to a client_id or None.

    Keeps the identity published downstream typed as ``str | None`` even
    when a caller supplies a pre-existing ``-> bool`` callable, so a raw
    ``True`` can never reach a log line posing as a client_id.

    :param result: Whatever an injected ``registry_check`` or ``verify``
        returned.
    :returns: The string unchanged when non-empty; ``UNKNOWN_CLIENT_ID``
        for a truthy non-string (a legacy bool-returning callable); None
        for anything falsy.
    """
    if isinstance(result, str):
        return result or None
    return UNKNOWN_CLIENT_ID if result else None


class ClientRecord(NamedTuple):
    """A registry client row: id, status, and creation time."""

    client_id: str
    status: Literal['active', 'revoked']
    created_at: str


class ClientExistsError(Exception):
    """Raised when minting a key for a client_id that already exists."""


class ClientNotFoundError(Exception):
    """Raised when revoking a client_id absent from the registry."""


def _dynamodb_client(dynamodb_client: Any = None, region: str | None = None) -> Any:
    """Return the injected boto3 client or build a default one.

    :param dynamodb_client: Pre-built boto3 DynamoDB client, or None.
    :param region: AWS region for a default client (optional). Ignored
        when ``dynamodb_client`` is supplied.
    :returns: A boto3 DynamoDB client.
    """
    if dynamodb_client is not None:
        return dynamodb_client
    # boto3 import deferred: it is an optional extra (libb-util[tokenauth])
    # carrying a measurable (~0.5s) import cost paid only when used.
    import boto3
    if region:
        return boto3.client('dynamodb', region_name=region)
    return boto3.client('dynamodb')


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest stored for a raw client key.

    :param raw_key: The plaintext key presented by a client.
    :returns: Lowercase hex SHA-256 digest.
    """
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def key_active_in_registry(
    key_sha256: str,
    *,
    table: str,
    region: str | None = None,
    dynamodb_client: Any = None,
) -> str | None:
    """Return the client_id a hashed key maps to, if that client is active.

    Queries the ``key_sha256-index`` GSI for a single match and reports the
    matched client's identity. Does not catch errors and does not cache --
    callers decide both. The GSI query already returns the whole row, so
    surfacing the identity costs nothing over the previous boolean and is
    what lets a caller attribute a request to a named client. An active row
    whose ``client_id`` is missing or empty denies, rather than authorizing
    an unattributable caller.

    :param key_sha256: SHA-256 hex digest of the presented key.
    :param table: DynamoDB registry table name.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: The matched ``client_id`` when the item exists and is
        active, else None.
    """
    client = _dynamodb_client(dynamodb_client, region)
    response = client.query(
        TableName=table,
        IndexName=KEY_SHA256_INDEX,
        KeyConditionExpression='key_sha256 = :h',
        ExpressionAttributeValues={':h': {'S': key_sha256}},
        Limit=1,
        )
    items = response.get('Items', [])
    if not items:
        return None
    if not items[0].get('active', {}).get('BOOL', False):
        return None
    return items[0].get('client_id', {}).get('S', '') or None


def verify_token(
    presented: str,
    *,
    table: str | None = None,
    static_token: str | None = None,
    region: str | None = None,
    dynamodb_client: Any = None,
    registry_check: Callable[[str], str | None] | None = None,
) -> str | None:
    """Authorize a presented key and return the identity, failing closed.

    The static break-glass token is checked first (constant time). The
    registry is then consulted via ``registry_check`` if given, else via a
    direct :func:`key_active_in_registry` call when ``table`` is provided.
    Any error in the registry path denies. If no path is configured -- no
    static token, no ``registry_check``, and no ``table`` -- the call
    denies; an open network-trust gate is an explicit caller decision,
    never a default here.

    To bind this to :class:`ApiTokenMiddleware`, wrap it with
    ``functools.partial(verify_token, static_token=..., registry_check=...)``.

    The returned identity is never the presented key: a credential must
    not reach the log line that records who called.

    :param presented: The raw key presented by the client.
    :param table: DynamoDB registry table name (optional). Used to build
        the default registry lookup when ``registry_check`` is not given.
    :param static_token: Constant-time break-glass token (optional).
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :param registry_check: Lookup called with the SHA-256 *digest* of the
        key (not the raw key) -- ``(key_sha256) -> str | None`` --
        replacing the default :func:`key_active_in_registry` call. This is
        the seam for a cached lookup: wrap :func:`key_active_in_registry`
        in a TTL cache and pass it here. When given, ``table``/``region``/
        ``dynamodb_client`` are not used.
    :returns: The authorized client identity, else None. A static-token
        match yields ``STATIC_TOKEN_CLIENT_ID`` so break-glass use is
        distinguishable in a log from a registered client; a legacy
        ``-> bool`` ``registry_check`` yields ``UNKNOWN_CLIENT_ID``.
    """
    if not presented:
        return None
    if static_token and secrets.compare_digest(presented, static_token):
        return STATIC_TOKEN_CLIENT_ID
    if registry_check is None and not table:
        return None
    try:
        if registry_check is not None:
            return _as_client_id(registry_check(hash_key(presented)))
        return key_active_in_registry(
            hash_key(presented), table=table, region=region,
            dynamodb_client=dynamodb_client)
    except Exception as exc:
        logger.warning('token registry lookup failed; denying (fail closed): %s', exc)
        return None


def mint_key(
    client_id: str,
    *,
    table: str,
    client_name: str | None = None,
    force: bool = False,
    region: str | None = None,
    dynamodb_client: Any = None,
) -> str:
    """Provision a client and return its freshly minted raw key.

    Generates a URL-safe key, stores only its SHA-256 hash, and refuses
    to overwrite an existing client unless ``force`` is set (rotation).
    The raw key is returned once and cannot be recovered afterward.

    :param client_id: Unique client identifier (the partition key).
    :param table: DynamoDB registry table name.
    :param client_name: Display name (defaults to client_id).
    :param force: Overwrite an existing client, rotating its key.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: The raw, unhashed key (shown once).
    :raises ClientExistsError: If client_id exists and force is False.
    """
    from botocore.exceptions import ClientError

    client = _dynamodb_client(dynamodb_client, region)
    raw_key = secrets.token_urlsafe(32)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    item = {
        'client_id': {'S': client_id},
        'client_name': {'S': client_name or client_id},
        'key_sha256': {'S': hash_key(raw_key)},
        'active': {'BOOL': True},
        'created_at': {'S': now},
        }
    kwargs = {'TableName': table, 'Item': item}
    if not force:
        kwargs['ConditionExpression'] = 'attribute_not_exists(client_id)'
    try:
        client.put_item(**kwargs)
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ClientExistsError(client_id) from exc
        raise
    return raw_key


def revoke_key(
    client_id: str,
    *,
    table: str,
    region: str | None = None,
    dynamodb_client: Any = None,
) -> None:
    """Disable a client by clearing its active flag.

    :param client_id: Client to deactivate.
    :param table: DynamoDB registry table name.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :raises ClientNotFoundError: If client_id is not in the registry.
    """
    from botocore.exceptions import ClientError

    client = _dynamodb_client(dynamodb_client, region)
    try:
        client.update_item(
            TableName=table,
            Key={'client_id': {'S': client_id}},
            UpdateExpression='SET active = :f',
            ExpressionAttributeValues={':f': {'BOOL': False}},
            ConditionExpression='attribute_exists(client_id)',
            )
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise ClientNotFoundError(client_id) from exc
        raise


def list_clients(
    *,
    table: str,
    region: str | None = None,
    dynamodb_client: Any = None,
) -> list[ClientRecord]:
    """Return every registered client, sorted by client_id.

    :param table: DynamoDB registry table name.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: Sorted :class:`ClientRecord` rows.
    """
    client = _dynamodb_client(dynamodb_client, region)
    paginator = client.get_paginator('scan')
    rows = []
    for page in paginator.paginate(TableName=table):
        rows.extend(ClientRecord(
                item.get('client_id', {}).get('S', ''),
                'active' if item.get('active', {}).get('BOOL') else 'revoked',
                item.get('created_at', {}).get('S', ''),
                ) for item in page.get('Items', []))
    return sorted(rows)


class ApiTokenMiddleware:
    """Raw ASGI middleware gating chosen path prefixes on a token.

    HTTP requests under ``protected_prefixes`` must present a key -- in the
    ``X-API-Key`` or ``Authorization: Bearer`` header -- that ``verify``
    authorizes; everything else passes through. ``verify`` is any
    ``(presented) -> str | None`` -- typically :func:`verify_token` bound
    to its config::

        verify = functools.partial(
            verify_token, static_token=TOKEN, registry_check=cached_lookup)
        app.add_middleware(
            ApiTokenMiddleware, protected_prefixes=('/api/',), verify=verify)

    The verifier runs in a worker thread and fails closed -- returning a
    falsy value or raising yields a 401.

    Raw ASGI, not ``BaseHTTPMiddleware``, so it never buffers a streaming
    body and depends on no web framework; only ``anyio`` is imported
    lazily (``libb-util[tokenauth]``). Note: only ``http`` scopes are
    gated -- ``websocket`` connections pass through, so do not place a
    WebSocket endpoint under a protected prefix expecting it to be gated.

    On success the authorized identity is published at
    ``scope['state']['client_id']`` before the wrapped app runs, so a
    downstream handler can attribute the request without re-reading the
    credential. A legacy ``-> bool`` verifier yields ``UNKNOWN_CLIENT_ID``
    there rather than a bare ``True``. A ``?key=`` query parameter is not
    an accepted credential source; see the module docstring.

    :param app: The wrapped ASGI application.
    :param protected_prefixes: Path prefixes that require a token.
    :param verify: ``(presented) -> str | None`` authorizer returning the
        identity.
    """

    def __init__(
        self,
        app: Any,
        *,
        protected_prefixes: Iterable[str],
        verify: Callable[[str], str | None],
    ) -> None:
        """Wrap an ASGI app with the configured credential check."""
        self.app = app
        self.protected_prefixes = tuple(protected_prefixes)
        self._verify = verify

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """Gate the request, offloading the blocking lookup to a thread."""
        import anyio

        if not self._guards(scope):
            await self.app(scope, receive, send)
            return

        presented = self._present_key(scope)
        client_id = None
        if presented:
            try:
                client_id = _as_client_id(
                    await anyio.to_thread.run_sync(self._verify, presented))
            except Exception as exc:
                logger.warning('authorization raised; denying (fail closed): %s', exc)
        if not client_id:
            await _send_unauthorized(send)
            return

        scope.setdefault('state', {})['client_id'] = client_id
        await self.app(scope, receive, send)

    def _guards(self, scope: dict) -> bool:
        """Return True if this request must be authorized."""
        if scope.get('type') != 'http':
            return False
        return scope.get('path', '').startswith(self.protected_prefixes)

    @staticmethod
    def _present_key(scope: dict) -> str | None:
        """Pull the key from the X-API-Key or Bearer header, header-only.

        The query string is never consulted. A credential in a URL is
        written verbatim into proxy, load-balancer and web-server access
        logs, so accepting ``?key=`` makes every request a disclosure.

        :param scope: The ASGI HTTP connection scope.
        :returns: The presented credential, or None when neither header
            carries one.
        """
        headers = {
            key.decode('latin-1').lower(): value.decode('latin-1')
            for key, value in scope.get('headers', [])
            }
        if headers.get('x-api-key'):
            return headers['x-api-key']
        authorization = headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            return authorization[7:] or None
        return None


async def _send_unauthorized(send: Any) -> None:
    """Emit a raw-ASGI 401 JSON response (no web-framework dependency)."""
    body = b'{"detail":"Unauthorized"}'
    await send({
        'type': 'http.response.start',
        'status': 401,
        'headers': [
            (b'content-type', b'application/json'),
            (b'content-length', str(len(body)).encode('latin-1')),
            ],
        })
    await send({'type': 'http.response.body', 'body': body})


def run_cli(argv: list[str] | None = None) -> int:
    """Generic add/revoke/list CLI over a client-key registry table.

    Run as ``python -m libb.tokenauth --table <name> add|revoke|list ...``
    or via the ``libb-tokenauth`` console script. The raw key from ``add``
    is printed once and cannot be recovered.

    :param argv: Argument list (defaults to sys.argv[1:]).
    :returns: Process exit code.
    """
    # argparse/sys deferred: this CLI is never reached when the module is
    # imported by a server, so its import cost stays off the hot path.
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog='libb.tokenauth')
    parser.add_argument('--table', required=True, help='registry table name')
    parser.add_argument('--region', default=None, help='AWS region (optional)')
    sub = parser.add_subparsers(dest='command', required=True)

    add = sub.add_parser('add', help='provision a client and mint a key')
    add.add_argument('client_id')
    add.add_argument('--name', default=None,
                     help='display name (defaults to client_id)')
    add.add_argument('--force', action='store_true',
                     help='overwrite an existing client (rotate its key)')

    revoke = sub.add_parser('revoke', help='deactivate a client')
    revoke.add_argument('client_id')

    sub.add_parser('list', help='list registered clients')

    args = parser.parse_args(argv)
    if args.command == 'add':
        try:
            raw_key = mint_key(args.client_id, table=args.table,
                               client_name=args.name, force=args.force,
                               region=args.region)
        except ClientExistsError:
            print(f'client {args.client_id!r} already exists '
                  f'(use --force to rotate its key)', file=sys.stderr)
            return 1
        print(f'client:  {args.client_id}')
        print(f'api key: {raw_key}')
        print('store this key now -- it cannot be recovered.')
        return 0
    if args.command == 'revoke':
        try:
            revoke_key(args.client_id, table=args.table, region=args.region)
        except ClientNotFoundError:
            print(f'client {args.client_id!r} not found', file=sys.stderr)
            return 1
        print(f'revoked {args.client_id}')
        return 0
    for record in list_clients(table=args.table, region=args.region):
        print(f'{record.client_id!r:34s} {record.status:8s} {record.created_at}')
    return 0


if __name__ == '__main__':
    raise SystemExit(run_cli())
