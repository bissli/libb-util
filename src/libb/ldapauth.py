"""Active Directory authentication via an LDAPS simple bind.

A small, framework-agnostic helper that binds to one or more domain
controllers over LDAPS, looks the user up by ``userPrincipalName``, and
returns their group CNs parsed from ``memberOf``. Servers, domain, and
TLS trust are all injected by the caller -- nothing is hardcoded -- so
the same code authenticates against any directory from a Linux container
or a domain-joined Windows host.

TLS is explicit: ``verify=True`` (the default) requires a validated
certificate, trusting ``ca_cert_file`` when given or the system trust
store otherwise; ``verify=False`` disables validation and logs a
warning. There is no silent downgrade to an unvalidated connection.

The ``ldap3`` dependency is optional: install ``libb-util[ldapauth]``.
"""
import logging
import ssl
from collections.abc import Iterable

logger = logging.getLogger(__name__)

__all__ = ['authenticate']

_USER_FILTER = (
    '(&(objectclass=user)(!(objectclass=computer))'
    '(userPrincipalName={user}@{domain}))')


def authenticate(
    user: str,
    password: str,
    *,
    servers: Iterable[str],
    domain: str,
    ca_cert_file: str | None = None,
    verify: bool = True,
    port: int = 636,
) -> tuple[str | None, list[str]]:
    """Bind to AD over LDAPS and return (user, group_cns) or (None, []).

    Tries each server in turn: invalid credentials deny immediately,
    while a server/connection error falls through to the next host. On a
    successful bind the user's ``memberOf`` group CNs are returned.

    :param user: sAMAccountName / UPN prefix (without the @domain part).
    :param password: The user's password.
    :param servers: Iterable of domain-controller hostnames.
    :param domain: AD DNS domain, e.g. 'corp.example.com'.
    :param ca_cert_file: PEM CA bundle to validate the server certificate
        against; when None the system trust store is used.
    :param verify: Require a validated TLS certificate (default True).
        When False, validation is disabled and a warning is logged.
    :param port: LDAPS port (default 636).
    :returns: (user, [group_cns]) on success, else (None, []).
    """
    if not user or not password:
        return None, []

    import ldap3
    from ldap3.core import exceptions as ldap_exceptions
    from ldap3.utils.conv import escape_filter_chars

    if verify:
        validate = ssl.CERT_REQUIRED
    else:
        logger.warning('LDAPS certificate validation disabled (verify=False)')
        validate = ssl.CERT_NONE
    tls = ldap3.Tls(ca_certs_file=ca_cert_file, validate=validate)

    treebase = ','.join('dc=' + part for part in domain.split('.'))
    user_filter = _USER_FILTER.format(
        user=escape_filter_chars(user), domain=domain)

    for host in servers:
        try:
            server = ldap3.Server(host, port=port, use_ssl=True, tls=tls)
            con = ldap3.Connection(
                server, f'{user}@{domain}', password, raise_exceptions=True)
            con.bind()
            con.search(search_base=treebase, search_filter=user_filter,
                       attributes=['memberOf'])
            entries = con.entries
            con.unbind()
            member_of = entries[0].memberOf if entries else []
            groups = [dn.split(',')[0][3:] for dn in member_of]
            logger.info('AD bind ok for %s groups=%d', user, len(groups))
            return user, groups
        except ldap_exceptions.LDAPInvalidCredentialsResult:
            logger.warning('invalid credentials for %s', user)
            return None, []
        except ldap_exceptions.LDAPException:
            logger.exception('AD bind failed against %s', host)
            continue
    return None, []
