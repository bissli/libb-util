import pathlib
import sys
import tempfile

import pytest

import libb
from libb import add_to_sys_path, cd, get_module_dir, scriptname


class TestGetModuleDir:
    """Tests for get_module_dir function."""

    def test_get_module_dir_with_module(self):
        # Pass actual module object
        result = get_module_dir(libb)
        assert isinstance(result, pathlib.Path)
        assert result.is_dir()
        assert 'libb' in str(result)

    def test_get_module_dir_without_args(self):
        # When called without args, gets caller's module dir
        result = get_module_dir()
        assert isinstance(result, pathlib.Path)
        assert result.is_dir()


class TestAddToSysPath:
    """Tests for add_to_sys_path function."""

    def test_add_to_sys_path(self):
        test_path = tempfile.gettempdir()
        add_to_sys_path(test_path)
        assert test_path in sys.path
        # Clean up
        if test_path in sys.path:
            sys.path.remove(test_path)

    def test_add_to_sys_path_with_relative(self):
        test_path = tempfile.gettempdir()
        add_to_sys_path(test_path, relative_path='subdir')
        expected = str(pathlib.Path(test_path) / 'subdir')
        assert expected in sys.path
        # Clean up
        if expected in sys.path:
            sys.path.remove(expected)

    def test_add_to_sys_path_no_args(self):
        # When called without path, uses caller's module directory
        original_path = sys.path.copy()
        add_to_sys_path()
        # Should have added a path
        assert len(sys.path) > len(original_path)
        # Clean up - remove first entry which was just added
        sys.path.pop(0)


class TestCd:
    """Tests for cd context manager."""

    def test_cd_changes_and_restores(self):
        original = pathlib.Path.cwd()
        with tempfile.TemporaryDirectory() as temp, cd(temp):
            # Inside context, cwd should be temp
            current = str(pathlib.Path.cwd().resolve())
            temp_resolved = str(pathlib.Path(temp).resolve())
            assert current == temp_resolved
        # After context, should be back to original
        assert pathlib.Path.cwd() == original


class TestScriptname:
    """Tests for scriptname function."""

    def test_scriptname_with_file(self):
        result = scriptname(__file__)
        assert result == 'test_path'

    def test_scriptname_no_args(self):
        # When called without args, uses sys.argv[0]
        result = scriptname()
        assert isinstance(result, str)

    def test_scriptname_with_path(self):
        result = scriptname('/some/path/to/script.py')
        assert result == 'script'

    def test_scriptname_no_extension(self):
        result = scriptname('/some/path/to/script')
        assert result == 'script'

    def test_scriptname_empty_task_and_argv(self, monkeypatch):
        # Test when task is empty and sys.argv[0] is also empty
        monkeypatch.setattr(sys, 'argv', [''])
        result = scriptname('')
        assert result == ''


if __name__ == '__main__':
    pytest.main([__file__])
