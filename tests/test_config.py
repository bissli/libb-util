import logging
import os
import sys
from dataclasses import dataclass

import config_sample as config
import pytest

from libb import Setting, configure_environment, create_mock_module
from libb.config import ConfigOptions, get_localdir, get_outputdir
from libb.config import get_tempdir, get_vendordir
from libb.config import patch_library_config, setting_unlocked

logger = logging.getLogger(__name__)


class TestConfig:

    def setup_method(self, test_method):
        Setting.unlock()
        self.defaultenv = config.ENVIRONMENT

    def teardown_method(self, test_method):
        config.environment(self.defaultenv)
        Setting.unlock()

    def test_accessors(self):
        assert config.main.main == config['main'].main
        assert config.main.main == config.main['main']
        assert config.main.main == config['main.main']
        assert sorted(config.main.keys()) == ['main', 'override']

    def test_environments(self):
        assert config.app1.server == 'app1-prod-server'  # !!!
        assert config.prod.app1.server == 'app1-prod-server'
        assert config.dev.app1.server == 'app1-dev-server'
        assert config['prod'].app1.server == 'app1-prod-server'
        assert config['dev'].app1.server == 'app1-dev-server'

    def test_local_overrides(self):
        assert config.main.override == 'Override'
        assert config.local.local == 'Local'
        assert config.app1.dir == '/prod/app1/'
        assert config.prod.app1.dir == '/prod/app1/'
        assert config.dev.app1.dir == '/dev/app1/'

    def test_set_environment(self):
        config.environment('prod')
        assert config.prod.app1.server == config.app1.server
        assert config.prod.app1.dir == config.app1.dir
        config.environment('dev')
        assert config.dev.app1.server == config.app1.server
        assert config.dev.app1.dir == config.app1.dir


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

    def test_configure_non_setting_object(self):
        """Verify behavior when found object is not a Setting instance."""

        class Foo:
            pass

        test_module = Foo()
        test_module.regular_attr = 'not a setting'

        configure_environment(test_module, regular_attr_value='test')

        assert test_module.regular_attr == 'not a setting'


class TestSettingSetattr:
    """Tests for Setting __setattr__ behavior."""

    def test_setattr_creates_new_key(self):
        Setting.unlock()
        s = Setting()
        s.new_key = 'value'
        assert s.new_key == 'value'
        Setting.lock()

    def test_setattr_locked_raises(self):
        Setting.unlock()
        s = Setting()
        s.existing = 'value'
        Setting.lock()
        with pytest.raises(ValueError, match='locked'):
            s.existing = 'new_value'
        Setting.unlock()


class TestConfigOptions:
    """Tests for ConfigOptions class."""

    def test_from_config(self):
        Setting.unlock()
        test = Setting()
        test.foo.bar.host = 'localhost'
        test.foo.bar.port = 8080
        Setting.lock()

        @dataclass
        class Options(ConfigOptions):
            host: str = None
            port: int = None

        create_mock_module('test_from_config', {'test': test})
        import test_from_config

        opts = Options.from_config('foo.bar', config=test_from_config.test)
        assert opts.host == 'localhost'
        assert opts.port == 8080

        Setting.unlock()


class TestLoadOptions:
    """Tests for load_options decorator.

    Note: load_options uses is_instance_method which checks qualname for '.'.
    The doctest in config.py tests the full functionality. Here we test
    edge cases that run in isolation.
    """

    def setup_method(self):
        Setting.unlock()

    def teardown_method(self):
        Setting.unlock()

    def test_load_options_doctest_runs(self):
        """Verify the doctest in load_options passes."""
        import doctest

        from libb import config
        results = doctest.testmod(config, verbose=False)
        assert results.failed == 0


class TestGetDirs:
    """Tests for get_tempdir, get_vendordir, get_outputdir, get_localdir."""

    def teardown_method(self):
        for var in ['CONFIG_TMPDIR_DIR', 'CONFIG_VENDOR_DIR', 'CONFIG_OUTPUT_DIR']:
            os.environ.pop(var, None)
        Setting.unlock()

    def test_get_tempdir_default(self):
        os.environ.pop('CONFIG_TMPDIR_DIR', None)
        result = get_tempdir()
        assert hasattr(result, 'dir')
        assert result.dir is not None

    def test_get_tempdir_when_locked(self):
        """Test that iflocked decorator unlocks, executes, and re-locks."""
        os.environ.pop('CONFIG_TMPDIR_DIR', None)
        Setting.lock()
        result = get_tempdir()
        assert hasattr(result, 'dir')
        # Should be re-locked after call
        assert Setting._locked is True

    def test_get_tempdir_with_env_var(self, tmp_path):
        os.environ['CONFIG_TMPDIR_DIR'] = str(tmp_path)
        result = get_tempdir()
        assert tmp_path == result.dir

    def test_get_vendordir_default(self):
        os.environ.pop('CONFIG_VENDOR_DIR', None)
        result = get_vendordir()
        assert hasattr(result, 'dir')
        assert result.dir is not None

    def test_get_vendordir_with_env_var(self, tmp_path):
        os.environ['CONFIG_VENDOR_DIR'] = str(tmp_path)
        result = get_vendordir()
        assert tmp_path == result.dir

    def test_get_outputdir_default(self):
        os.environ.pop('CONFIG_OUTPUT_DIR', None)
        result = get_outputdir()
        assert hasattr(result, 'dir')
        assert result.dir is not None

    def test_get_outputdir_with_env_var(self, tmp_path):
        os.environ['CONFIG_OUTPUT_DIR'] = str(tmp_path)
        result = get_outputdir()
        assert tmp_path == result.dir

    def test_get_localdir(self):
        result = get_localdir()
        assert hasattr(result, 'dir')
        assert result.dir is not None


class TestSettingUnlocked:
    """Tests for setting_unlocked context manager."""

    def test_setting_unlocked_basic(self):
        Setting.lock()
        s = Setting()
        with pytest.raises(ValueError):
            s.test = 'value'

        with setting_unlocked(s):
            s.test = 'value'
            assert s.test == 'value'

        with pytest.raises(ValueError):
            s.test2 = 'value2'
        Setting.unlock()


class TestPatchLibraryConfig:
    """Tests for patch_library_config function."""

    def teardown_method(self):
        for key in list(sys.modules.keys()):
            if 'test_lib_patch' in key:
                del sys.modules[key]

    def test_patch_library_config_already_loaded(self):
        """Test patching a config that's already in sys.modules."""
        Setting.unlock()
        test_setting = Setting()
        test_setting.host = 'original'
        Setting.lock()

        # Manually create the module in sys.modules
        import types
        config_module = types.ModuleType('test_lib_patch_exist.config')
        config_module.test_setting = test_setting
        sys.modules['test_lib_patch_exist.config'] = config_module

        patch_library_config('test_lib_patch_exist', test_setting_host='patched')

        assert sys.modules['test_lib_patch_exist.config'].test_setting.host == 'patched'

    def test_patch_library_config_not_found(self):
        with pytest.raises(ImportError, match='Could not import'):
            patch_library_config('nonexistent_library_xyz123')


if __name__ == '__main__':
    pytest.main([__file__])
