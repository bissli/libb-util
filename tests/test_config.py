import config_sample as config
import pytest


class TestConfig():

    def setup_method(self, test_method):
        self.defaultenv = config.ENVIRONMENT

    def teardown_method(self, test_method):
        config.environment(self.defaultenv)

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


if __name__ == '__main__':
    pytest.main([__file__])
