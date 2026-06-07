"""Tests for the ldapauth module."""

import ssl
from unittest import mock

import pytest

ldap3 = pytest.importorskip('ldap3')

from libb import ldapauth


class FakeEntry:
    """Stand-in for an ldap3 search entry exposing memberOf."""

    def __init__(self, member_of):
        self.memberOf = member_of


class FakeConnection:
    """Stand-in for an ldap3 Connection with a controllable bind/search."""

    def __init__(self, entries=None, bind_error=None):
        self._entries = entries if entries is not None else []
        self._bind_error = bind_error

    def bind(self):
        if self._bind_error:
            raise self._bind_error

    def search(self, **kwargs):
        return True

    @property
    def entries(self):
        return self._entries

    def unbind(self):
        return True


def _patch(connection_side_effect=None, connection_return=None):
    """Patch ldap3.Server/Tls/Connection for a single authenticate call."""
    server = mock.patch.object(ldap3, 'Server', return_value=mock.Mock())
    tls = mock.patch.object(ldap3, 'Tls', return_value=mock.Mock())
    if connection_side_effect is not None:
        conn = mock.patch.object(ldap3, 'Connection',
                                 side_effect=connection_side_effect)
    else:
        conn = mock.patch.object(ldap3, 'Connection',
                                 return_value=connection_return)
    return server, tls, conn


class TestAuthenticate:
    """Tests for ldapauth.authenticate."""

    def test_success_returns_user_and_group_cns(self):
        """Verify a successful bind returns the user and parsed group CNs."""
        fake = FakeConnection(entries=[FakeEntry(
            ['CN=Admins,OU=Groups,DC=corp', 'CN=Users,DC=corp'])])
        server, tls, conn = _patch(connection_return=fake)
        with server, tls, conn:
            user, groups = ldapauth.authenticate(
                'alice', 'pw', servers=['dc1'], domain='corp.example.com')
        assert user == 'alice'
        assert groups == ['Admins', 'Users']

    def test_empty_credentials_short_circuit(self):
        """Verify blank user or password denies without contacting AD."""
        assert ldapauth.authenticate(
            '', 'pw', servers=['dc1'], domain='corp.example.com') == (None, [])
        assert ldapauth.authenticate(
            'alice', '', servers=['dc1'], domain='corp.example.com') == (None, [])

    def test_invalid_credentials_deny_immediately(self):
        """Verify invalid credentials return (None, [])."""
        fake = FakeConnection(
            bind_error=ldap3.core.exceptions.LDAPInvalidCredentialsResult())
        server, tls, conn = _patch(connection_return=fake)
        with server, tls, conn:
            assert ldapauth.authenticate(
                'alice', 'bad', servers=['dc1'],
                domain='corp.example.com') == (None, [])

    def test_server_error_falls_through_to_next(self):
        """Verify a server error tries the next server before succeeding."""
        good = FakeConnection(entries=[FakeEntry(['CN=Users,DC=corp'])])
        side = [ldap3.core.exceptions.LDAPSocketOpenError('down'), good]
        server, tls, conn = _patch(connection_side_effect=side)
        with server, tls, conn:
            user, groups = ldapauth.authenticate(
                'alice', 'pw', servers=['dc1', 'dc2'],
                domain='corp.example.com')
        assert (user, groups) == ('alice', ['Users'])

    def test_all_servers_failing_denies(self):
        """Verify exhausting all servers with errors returns (None, [])."""
        side = [ldap3.core.exceptions.LDAPSocketOpenError('down'),
                ldap3.core.exceptions.LDAPSocketOpenError('down')]
        server, tls, conn = _patch(connection_side_effect=side)
        with server, tls, conn:
            assert ldapauth.authenticate(
                'alice', 'pw', servers=['dc1', 'dc2'],
                domain='corp.example.com') == (None, [])

    def test_no_entries_returns_empty_groups(self):
        """Verify a bound user with no search entry yields no groups."""
        fake = FakeConnection(entries=[])
        server, tls, conn = _patch(connection_return=fake)
        with server, tls, conn:
            assert ldapauth.authenticate(
                'alice', 'pw', servers=['dc1'],
                domain='corp.example.com') == ('alice', [])

    def test_verify_true_requires_validated_cert(self):
        """Verify verify=True builds TLS with CERT_REQUIRED."""
        fake = FakeConnection(entries=[])
        with mock.patch.object(ldap3, 'Server', return_value=mock.Mock()), \
                mock.patch.object(ldap3, 'Connection', return_value=fake), \
                mock.patch.object(ldap3, 'Tls', return_value=mock.Mock()) as tls:
            ldapauth.authenticate('alice', 'pw', servers=['dc1'],
                                  domain='corp.example.com', verify=True)
        assert tls.call_args.kwargs['validate'] == ssl.CERT_REQUIRED

    def test_verify_false_disables_validation(self):
        """Verify verify=False builds TLS with CERT_NONE."""
        fake = FakeConnection(entries=[])
        with mock.patch.object(ldap3, 'Server', return_value=mock.Mock()), \
                mock.patch.object(ldap3, 'Connection', return_value=fake), \
                mock.patch.object(ldap3, 'Tls', return_value=mock.Mock()) as tls:
            ldapauth.authenticate('alice', 'pw', servers=['dc1'],
                                  domain='corp.example.com', verify=False)
        assert tls.call_args.kwargs['validate'] == ssl.CERT_NONE
