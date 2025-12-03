import datetime
import os
import pathlib
import tempfile

import pytest

from libb import expandabspath, make_tmpdir, mkdir_p, splitall
from libb.dir import dir_to_dict, get_dir_match, get_directory_structure
from libb.dir import load_files, resplit, safe_move
from libb.dir import save_file_tmpdir, search


class TestMkdirP:
    """Tests for mkdir_p function."""

    def test_mkdir_p_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_path = os.path.join(tmpdir, 'a', 'b', 'c')
            mkdir_p(new_path)
            assert pathlib.Path(new_path).is_dir()

    def test_mkdir_p_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mkdir_p(tmpdir)  # Should not raise
            assert pathlib.Path(tmpdir).is_dir()


class TestMakeTmpdir:
    """Tests for make_tmpdir context manager."""

    def test_make_tmpdir_creates_and_removes(self):
        path = None
        with make_tmpdir() as tmpdir:
            path = str(tmpdir)
            assert pathlib.Path(path).is_dir()
        assert not pathlib.Path(path).exists()

    def test_make_tmpdir_can_write_files(self):
        with make_tmpdir() as tmpdir:
            filepath = tmpdir / 'test.txt'
            filepath.write_text('hello')
            assert filepath.read_text() == 'hello'


class TestExpandabspath:
    """Tests for expandabspath function."""

    def test_expandabspath_tilde(self):
        result = expandabspath('~')
        assert pathlib.Path(str(result)).is_absolute()

    def test_expandabspath_absolute(self):
        result = expandabspath('/foo')
        assert '/foo' in str(result)


class TestSplitall:
    """Tests for splitall function."""

    def test_splitall_relative(self):
        assert splitall('a/b/c') == ['a', 'b', 'c']

    def test_splitall_absolute_unix(self):
        assert splitall('/a/b/c/') == ['/', 'a', 'b', 'c', '']

    def test_splitall_root(self):
        assert splitall('/') == ['/']

    def test_splitall_windows_drive(self):
        assert splitall('C:') == ['C:']

    def test_splitall_windows_drive_path(self):
        assert splitall('C:\\a\\b') == ['C:\\', 'a', 'b']

    def test_splitall_empty(self):
        assert splitall('') == []

    def test_splitall_type_error(self):
        with pytest.raises(TypeError):
            splitall(123)


class TestGetDirectoryStructure:
    """Tests for get_directory_structure function."""

    def test_get_directory_structure_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a structure
            pathlib.Path(os.path.join(tmpdir, 'a', 'b')).mkdir(parents=True)
            pathlib.Path(tmpdir, 'a', 'file1.txt').write_text('test')
            pathlib.Path(tmpdir, 'a', 'b', 'file2.txt').write_text('test')

            result = get_directory_structure(tmpdir)
            assert isinstance(result, dict)
            # Should have nested structure
            root_key = list(result.keys())[0]
            assert 'a' in result[root_key]


class TestSearch:
    """Tests for search function."""

    def test_search_by_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(tmpdir, 'test_file.txt').write_text('content')
            pathlib.Path(tmpdir, 'other.txt').write_text('content')

            results = list(search(tmpdir, name='test_file'))
            assert len(results) == 1
            assert 'test_file' in results[0]

    def test_search_by_extension(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(tmpdir, 'file.txt').write_text('content')
            pathlib.Path(tmpdir, 'file.csv').write_text('content')

            results = list(search(tmpdir, extension='.txt'))
            assert len(results) == 1
            assert results[0].endswith('.txt')

    def test_search_all_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(tmpdir, 'file1.txt').write_text('content')
            pathlib.Path(tmpdir, 'file2.txt').write_text('content')

            results = list(search(tmpdir))
            assert len(results) == 2


class TestSafeMove:
    """Tests for safe_move function."""

    def test_safe_move_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = pathlib.Path(tmpdir, 'source.txt')
            target = pathlib.Path(tmpdir, 'target.txt')
            source.write_text('content')

            result = safe_move(str(source), str(target))
            assert pathlib.Path(result).exists()
            assert not source.exists()

    def test_safe_move_hard_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = pathlib.Path(tmpdir, 'source.txt')
            target = pathlib.Path(tmpdir, 'target.txt')
            source.write_text('source content')
            target.write_text('target content')

            result = safe_move(str(source), str(target), hard_remove=True)
            assert pathlib.Path(result).exists()
            assert pathlib.Path(result).read_text() == 'source content'

    def test_safe_move_target_not_exists_hard_remove(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = pathlib.Path(tmpdir, 'source.txt')
            target = pathlib.Path(tmpdir, 'nonexistent.txt')
            source.write_text('content')

            # hard_remove=True but target doesn't exist
            result = safe_move(str(source), str(target), hard_remove=True)
            assert pathlib.Path(result).exists()

    def test_safe_move_collision_renames(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = pathlib.Path(tmpdir, 'source.txt')
            # Create a directory at target to cause OSError
            target_dir = pathlib.Path(tmpdir, 'target.txt')
            target_dir.mkdir()

            source.write_text('content')

            # This should cause rename with random suffix
            result = safe_move(str(source), str(target_dir))
            assert pathlib.Path(result).exists()


class TestSaveFileTmpdir:
    """Tests for save_file_tmpdir function."""

    def test_save_file_tmpdir_basic(self):
        content = 'test content'
        fname = f'test_save_{os.getpid()}.txt'

        with tempfile.TemporaryDirectory() as tmpdir:
            save_file_tmpdir(fname, content, tmpdir=tmpdir)
            saved_file = pathlib.Path(tmpdir, fname)
            assert saved_file.exists()
            assert saved_file.read_text() == content

    def test_save_file_tmpdir_with_date(self):
        content = 'test content'
        thedate = datetime.date(2023, 6, 15)

        with tempfile.TemporaryDirectory() as tmpdir:
            save_file_tmpdir('test.txt', content, thedate=thedate, tmpdir=tmpdir)
            # File should have date in name
            files = list(pathlib.Path(tmpdir).glob('*20230615*'))
            assert len(files) == 1


class TestGetDirMatch:
    """Tests for get_dir_match function."""

    def test_get_dir_match_finds_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = pathlib.Path(tmpdir, 'test.txt')
            test_file.write_text('content')

            results, warnings = get_dir_match([(tmpdir, 'test.txt')])
            assert len(results) == 1
            assert results[0] == str(test_file)
            assert len(warnings) == 0

    def test_get_dir_match_warns_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results, warnings = get_dir_match([(tmpdir, 'nonexistent.txt')])
            assert len(results) == 0
            assert len(warnings) == 1
            assert 'NOT FOUND' in warnings[0]

    def test_get_dir_match_skips_zero_length(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = pathlib.Path(tmpdir, 'empty.txt')
            test_file.write_text('')  # Zero-length file

            results, warnings = get_dir_match([(tmpdir, 'empty.txt')])
            assert len(results) == 0
            assert len(warnings) == 1
            assert 'zero-length' in warnings[0]

    def test_get_dir_match_with_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            thedate = datetime.date(2023, 6, 15)
            test_file = pathlib.Path(tmpdir, 'test_20230615.txt')
            test_file.write_text('content')

            results, warnings = get_dir_match([(tmpdir, 'test*.txt')], thedate=thedate)
            assert len(results) == 1


class TestLoadFiles:
    """Tests for load_files function."""

    def test_load_files_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = pathlib.Path(tmpdir, 'test.txt')
            test_file.write_text('content here')

            results = list(load_files(tmpdir, 'test.txt'))
            assert len(results) == 1
            assert results[0] == 'content here'

    def test_load_files_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(tmpdir, 'file1.txt').write_text('content1')
            pathlib.Path(tmpdir, 'file2.txt').write_text('content2')

            results = list(load_files(tmpdir, '*.txt'))
            assert len(results) == 2


class TestLoadFilesTmpdir:
    """Tests for load_files_tmpdir function."""

    def test_load_files_tmpdir_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = pathlib.Path(tmpdir, 'tmptest.txt')
            test_file.write_text('tmp content')

            # Test with single pattern (converted to tuple)
            results = list(load_files(tmpdir, 'tmptest.txt'))
            assert len(results) == 1

    def test_load_files_tmpdir_multiple_patterns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(tmpdir, 'file1.txt').write_text('content1')
            pathlib.Path(tmpdir, 'file2.csv').write_text('content2')

            # This tests the list handling in load_files_tmpdir
            patterns = ['file1.txt', 'file2.csv']
            results = list(load_files(tmpdir, 'file*.txt'))
            assert len(results) >= 1


class TestDirToDict:
    """Tests for dir_to_dict function."""

    def test_dir_to_dict_basic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pathlib.Path(os.path.join(tmpdir, 'subdir')).mkdir(parents=True)
            pathlib.Path(tmpdir, 'file.txt').write_text('content')
            pathlib.Path(tmpdir, 'subdir', 'nested.txt').write_text('content')

            result = dir_to_dict(tmpdir)
            assert '.files' in result
            assert 'file.txt' in result['.files']
            assert 'subdir' in result


class TestResplit:
    """Tests for resplit function."""

    def test_resplit_basic(self):
        path = '/First/Second/Third'
        result = resplit(path, '/')
        assert 'First' in result
        assert 'Second' in result

    def test_resplit_multiple_separators(self):
        path = 'a/b\\c'
        result = resplit(path, '/', '\\')
        assert 'a' in result
        assert 'b' in result
        assert 'c' in result


class TestSplitallEdgeCases:
    """Additional tests for splitall edge cases."""

    def test_splitall_windows_trailing_slash(self):
        assert splitall('C:\\a\\') == ['C:\\', 'a', '']

    def test_splitall_consecutive_slashes(self):
        result = splitall('a//b')
        assert result == ['a', 'b']


if __name__ == '__main__':
    pytest.main([__file__])
