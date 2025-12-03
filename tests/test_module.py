import sys

import pytest

from libb import Setting, create_instance, create_mock_module, get_class
from libb import get_module


class TestGetModule:
    """Tests for get_module function."""

    def test_get_module_builtin(self):
        result = get_module('os')
        import os
        assert result is os

    def test_get_module_dotted(self):
        result = get_module('os.path')
        import os.path
        assert result is os.path

    def test_get_module_nonexistent_raises(self):
        with pytest.raises(ModuleNotFoundError):
            get_module('nonexistent_module_xyz')


class TestGetClass:
    """Tests for get_class function."""

    def test_get_class_with_module(self):
        cls = get_class('libb.Setting')
        assert cls is Setting


class TestCreateMockModule:
    """Tests for create_mock_module function."""

    def test_create_mock_module_basic(self):
        create_mock_module('test_mock_module', {'x': 123, 'y': 'hello'})
        import test_mock_module
        assert test_mock_module.x == 123
        assert test_mock_module.y == 'hello'
        # Cleanup
        del sys.modules['test_mock_module']

    def test_create_mock_module_empty(self):
        create_mock_module('test_empty_module')
        assert 'test_empty_module' in sys.modules
        # Cleanup
        del sys.modules['test_empty_module']

    def test_create_mock_module_with_setting(self):
        create_mock_module('test_config_module', {'foo': Setting(bar=1)})
        import test_config_module
        assert test_config_module.foo.bar == 1
        # Cleanup
        del sys.modules['test_config_module']


class TestCreateInstance:
    """Tests for create_instance function."""

    def test_create_instance_with_kwargs(self):
        instance = create_instance('libb.Setting', foo=42, bar='baz')
        assert instance.foo == 42
        assert instance.bar == 'baz'

    def test_create_instance_empty(self):
        instance = create_instance('libb.Setting')
        assert isinstance(instance, dict)


if __name__ == '__main__':
    pytest.main([__file__])
