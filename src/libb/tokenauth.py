"""Token-registry auth: per-client API keys backed by a DynamoDB table.

A small, framework-agnostic core for gating machine endpoints (MCP / API)
on per-client keys. Keys are minted once, stored only as SHA-256 hashes,
and looked up by a ``key_sha256`` global secondary index; a client is
allowed only while its item is ``active``.

The table name, AWS region, and boto3 client are all injected by the
caller -- nothing is hardcoded -- so the same code serves any ``<name>``
registry table on Fargate (ambient task role) or a host passing explicit
credentials. Validation fails closed and compares the optional static
break-glass token in constant time. No caching is done here: callers wrap
:func:`key_active_in_registry` in whatever cache suits their runtime.

Expected table shape::

    client_id   (S)  -- partition key
    client_name (S)
    key_sha256  (S)  -- GSI 'key_sha256-index', projection ALL
    active      (BOOL)
    created_at  (S)  -- ISO-8601 UTC

The ``boto3`` dependency is optional: install ``libb-util[tokenauth]``.
"""
import datetime
import hashlib
import logging
import secrets
from collections.abc import Callable

logger = logging.getLogger(__name__)

__all__ = [
    'KEY_SHA256_INDEX',
    'ClientExistsError',
    'ClientNotFoundError',
    'hash_key',
    'key_active_in_registry',
    'verify_token',
    'mint_key',
    'revoke_key',
    'list_clients',
    'ApiTokenMiddleware',
]

KEY_SHA256_INDEX = 'key_sha256-index'


class ClientExistsError(Exception):
    """Raised when minting a key for a client_id that already exists."""


class ClientNotFoundError(Exception):
    """Raised when revoking a client_id absent from the registry."""


def _dynamodb_client(dynamodb_client=None, region: str | None = None):
    """Return the injected boto3 client or build a default one.

    :param dynamodb_client: Pre-built boto3 DynamoDB client, or None.
    :param region: AWS region for a default client (optional).
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
    dynamodb_client=None,
) -> bool:
    """Return True iff a hashed key maps to an active client.

    Queries the ``key_sha256-index`` GSI for a single match and reports
    its ``active`` flag. Does not catch errors and does not cache --
    callers decide both.

    :param key_sha256: SHA-256 hex digest of the presented key.
    :param table: DynamoDB registry table name.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: True if a matching client item is active.
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
        return False
    return items[0].get('active', {}).get('BOOL', False)


def verify_token(
    presented: str,
    *,
    table: str | None = None,
    static_token: str | None = None,
    region: str | None = None,
    dynamodb_client=None,
) -> bool:
    """Authorize a presented key, failing closed.

    Checks the optional static break-glass token first (constant time),
    then the registry. Any registry error denies. If neither a static
    token nor a table is configured the call denies -- an open
    network-trust gate is an explicit caller decision, never a default
    here.

    :param presented: The raw key presented by the client.
    :param table: DynamoDB registry table name (optional).
    :param static_token: Constant-time break-glass token (optional).
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: True if the presented key is authorized.
    """
    if not presented:
        return False
    if static_token and secrets.compare_digest(presented, static_token):
        return True
    if not table:
        return False
    try:
        return key_active_in_registry(
            hash_key(presented), table=table, region=region,
            dynamodb_client=dynamodb_client)
    except Exception as exc:
        logger.warning(f'token registry lookup failed; denying (fail closed): {exc}')
        return False


def mint_key(
    client_id: str,
    *,
    table: str,
    client_name: str | None = None,
    force: bool = False,
    region: str | None = None,
    dynamodb_client=None,
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
    dynamodb_client=None,
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
    dynamodb_client=None,
) -> list[tuple[str, str, str]]:
    """Return every registered client as (client_id, status, created_at).

    :param table: DynamoDB registry table name.
    :param region: AWS region for a default boto3 client (optional).
    :param dynamodb_client: Injected boto3 DynamoDB client (optional).
    :returns: Sorted (client_id, 'active'|'revoked', created_at) tuples.
    """
    client = _dynamodb_client(dynamodb_client, region)
    paginator = client.get_paginator('scan')
    rows = []
    for page in paginator.paginate(TableName=table):
        rows.extend((
                item.get('client_id', {}).get('S', ''),
                'active' if item.get('active', {}).get('BOOL') else 'revoked',
                item.get('created_at', {}).get('S', ''),
                ) for item in page.get('Items', []))
    return sorted(rows)


class ApiTokenMiddleware:
    """Raw ASGI middleware gating chosen path prefixes on a token.

    Requests under ``protected_prefixes`` must present a key (``X-API-Key``
    header, ``Authorization: Bearer``, or ``?key=``); all else passes
    through, as does any request when neither a static token nor a table
    is configured. Authorization runs through :func:`verify_token` unless
    a ``verify`` callable is injected (e.g. to add caching). Raw ASGI, not
    ``BaseHTTPMiddleware``, so it never buffers a streaming body;
    ``starlette`` and ``anyio`` import lazily (``libb-util[tokenauth]``).

    :param app: The wrapped ASGI application.
    :param protected_prefixes: Path prefixes that require a token.
    :param table: DynamoDB registry table name (optional).
    :param static_token: Constant-time break-glass token (optional).
    :param region: AWS region for a default boto3 client (optional).
    :param verify: Custom ``(presented) -> bool`` authorizer; defaults to
        :func:`verify_token` over the table/static token/region.
    """

    def __init__(
        self,
        app,
        *,
        protected_prefixes: tuple[str, ...],
        table: str | None = None,
        static_token: str | None = None,
        region: str | None = None,
        verify: Callable[[str], bool] | None = None,
    ) -> None:
        """Wrap an ASGI app with the configured credential checks."""
        self.app = app
        self.protected_prefixes = tuple(protected_prefixes)
        self.table = table
        self.static_token = static_token
        self.region = region
        self._verify = verify

    async def __call__(self, scope, receive, send) -> None:
        """Gate the request, offloading the blocking lookup to a thread."""
        import anyio

        if not self._guards(scope):
            await self.app(scope, receive, send)
            return

        presented = self._present_key(scope)
        authorized = bool(presented) and await anyio.to_thread.run_sync(
            self._authorize, presented)
        if not authorized:
            from starlette.responses import JSONResponse
            response = JSONResponse({'detail': 'Unauthorized'}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _guards(self, scope) -> bool:
        """Return True if this request must be authorized."""
        if scope['type'] != 'http':
            return False
        if not self._verify and not self.static_token and not self.table:
            return False
        return scope['path'].startswith(self.protected_prefixes)

    @staticmethod
    def _present_key(scope) -> str | None:
        """Pull the key from the X-API-Key, Bearer, or ?key= sources."""
        from urllib.parse import parse_qs

        headers = {
            key.decode('latin-1').lower(): value.decode('latin-1')
            for key, value in scope.get('headers', [])
            }
        if headers.get('x-api-key'):
            return headers['x-api-key']
        authorization = headers.get('authorization', '')
        if authorization.lower().startswith('bearer '):
            return authorization[7:]
        query = parse_qs(scope.get('query_string', b'').decode('latin-1'))
        return (query.get('key') or [None])[0]

    def _authorize(self, presented: str) -> bool:
        """Authorize a key via the injected or default verifier."""
        if self._verify is not None:
            return self._verify(presented)
        return verify_token(
            presented, table=self.table, static_token=self.static_token,
            region=self.region)


def _admin_main(argv: list[str] | None = None) -> int:
    """Generic add/revoke/list CLI over a client-key registry table.

    Run as ``python -m libb.tokenauth --table <name> add|revoke|list ...``.
    The raw key from ``add`` is printed once and cannot be recovered.

    :param argv: Argument list (defaults to sys.argv[1:]).
    :returns: Process exit code.
    """
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
    for client_id, status, created_at in list_clients(
            table=args.table, region=args.region):
        print(f'{client_id:32s} {status:8s} {created_at}')
    return 0


if __name__ == '__main__':
    raise SystemExit(_admin_main())
