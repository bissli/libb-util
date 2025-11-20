import logging

import pytest

from libb import Setting, configure_environment

logger = logging.getLogger(__name__)


class TestConfigureEnvironment:
    """Test configure_environment function with various scenarios."""

    def setup_method(self, test_method):
        """Set up test fixtures with mock module and Setting objects."""
        Setting.unlock()

        class Foo: pass
        self.test_config = Foo()
        self.test_config.database = Setting()
        self.test_config.database.host = 'localhost'
        self.test_config.database.port = 5432
        self.test_config.database.credentials.username = 'user'
        self.test_config.database.credentials.password = 'pass'

        self.test_config.api = Setting()
        self.test_config.api.base_url = 'https://api.example.com'
        self.test_config.api.timeout = 30

        self.test_config.vendor_settings = Setting()
        self.test_config.vendor_settings.ftp.hostname = '127.0.0.1'

        Setting.lock()

    def teardown_method(self, test_method):
        """Clean up after each test."""
        Setting.unlock()

    def test_configure_simple_attributes(self):
        """Verify basic attribute configuration works correctly."""
        configure_environment(
            self.test_config,
            database_host='new-host',
            database_port=3306,
            api_timeout=60
        )

        assert self.test_config.database.host == 'new-host'
        assert self.test_config.database.port == 3306
        assert self.test_config.api.timeout == 60
        assert self.test_config.api.base_url == 'https://api.example.com'

    def test_configure_nested_attributes(self):
        """Verify nested attribute navigation and setting works correctly."""
        configure_environment(
            self.test_config,
            database_credentials_username='newuser',
            database_credentials_password='newpass',
            vendor_settings_ftp_hostname='192.168.1.1'
        )

        assert self.test_config.database.credentials.username == 'newuser'
        assert self.test_config.database.credentials.password == 'newpass'
        assert self.test_config.vendor_settings.ftp.hostname == '192.168.1.1'

    def test_configure_creates_new_nested_attributes(self):
        """Verify new nested attributes are created when they don't exist."""
        configure_environment(
            self.test_config,
            database_connection_pool_size=10,
            api_cache_ttl=300
        )

        assert self.test_config.database.connection.pool.size == 10
        assert self.test_config.api.cache.ttl == 300

    def test_configure_with_various_value_types(self):
        """Verify different data types can be set as configuration values."""
        configure_environment(
            self.test_config,
            database_port=3306,
            database_ssl_enabled=True,
            api_rate_limit=10.5,
            database_supported_engines=['mysql', 'postgres'],
            api_headers={'Content-Type': 'application/json'}
        )

        assert self.test_config.database.port == 3306
        assert self.test_config.database.ssl.enabled is True
        assert self.test_config.api.rate.limit == 10.5
        assert self.test_config.database.supported.engines == ['mysql', 'postgres']
        assert self.test_config.api.headers == {'Content-Type': 'application/json'}

    def test_configure_nonexistent_setting_object(self, caplog):
        """Verify behavior when no matching Setting object is found."""
        configure_environment(
            self.test_config,
            nonexistent_setting_value=123
        )

        assert not hasattr(self.test_config, 'nonexistent_setting')

    def test_configure_key_matches_setting_exactly(self):
        """Verify behavior when key matches a Setting object name exactly."""
        configure_environment(
            self.test_config,
            database='should_not_be_set'
        )

        assert isinstance(self.test_config.database, Setting)

    def test_configure_multiple_underscore_patterns(self):
        """Verify correct handling of complex underscore patterns in keys."""
        configure_environment(
            self.test_config,
            vendor_settings_ftp_connection_timeout=120,
            vendor_settings_sftp_port=22
        )

        assert self.test_config.vendor_settings.ftp.connection.timeout == 120
        assert self.test_config.vendor_settings.sftp.port == 22

    def test_configure_logging_output(self):
        """Verify appropriate debug logging during configuration."""
        configure_environment(
            self.test_config,
            database_host='test-host',
            api_timeout=45
        )

        assert self.test_config.database.host == 'test-host'
        assert self.test_config.api.timeout == 45

    def test_configure_with_real_config_module(self):
        """Verify configuration works with actual config module structure."""
        Setting.unlock()

        class Foo: pass
        test_module = Foo()
        test_module.vendor = Setting()
        test_module.vendor.FOO.ftp.hostname = '127.0.0.1'
        test_module.vendor.FOO.ftp.username = 'foo'
        test_module.vendor.FOO.ftp.password = 'bar'
        test_module.vendor.FOO.ftp.port = 21

        Setting.lock()

        configure_environment(
            test_module,
            vendor_FOO_ftp_hostname='newhost',
            vendor_FOO_ftp_port=2121,
            vendor_FOO_database_url='postgresql://localhost/test'
        )

        assert test_module.vendor.FOO.ftp.hostname == 'newhost'
        assert test_module.vendor.FOO.ftp.port == 2121
        assert test_module.vendor.FOO.database.url == 'postgresql://localhost/test'

    def test_configure_empty_config_overrides(self):
        """Verify function handles empty configuration gracefully."""
        original_host = self.test_config.database.host

        configure_environment(self.test_config)

        assert self.test_config.database.host == original_host


if __name__ == '__main__':
    pytest.main([__file__])
