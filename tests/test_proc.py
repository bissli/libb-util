import psutil
import pytest

from libb import kill_proc, process_by_name, process_by_name_and_port


def _find_listening_process():
    """Find any process with a listening connection for testing."""
    for proc in psutil.process_iter():
        try:
            for conn in proc.connections():
                if conn.status == 'LISTEN':
                    return proc.name(), conn.laddr.port
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
    return None, None


class TestProcessByName:
    """Tests for process_by_name function."""

    def test_process_by_name_no_match(self):
        # Test with non-existent process name
        result = list(process_by_name('nonexistent_process_xyz_123'))
        assert result == []

    def test_process_by_name_returns_generator(self):
        # Should return a generator
        result = process_by_name('python')
        assert hasattr(result, '__iter__')

    def test_process_by_name_with_listening_process(self):
        # Test with a real listening process
        name, port = _find_listening_process()
        if name is None:
            pytest.skip('No listening process found')
        result = list(process_by_name(name))
        assert len(result) >= 1


class TestProcessByNameAndPort:
    """Tests for process_by_name_and_port function."""

    def test_process_by_name_and_port_no_match(self):
        # Test with non-existent process
        result = process_by_name_and_port('nonexistent_process_xyz', 9999)
        assert result is None

    def test_process_by_name_and_port_with_listening_process(self):
        # Test with a real listening process
        name, port = _find_listening_process()
        if name is None:
            pytest.skip('No listening process found')
        result = process_by_name_and_port(name, port)
        assert result is not None


class TestKillProc:
    """Tests for kill_proc function."""

    def test_kill_proc_requires_name_or_version(self):
        with pytest.raises(AssertionError, match='Need something to kill'):
            kill_proc()

    def test_kill_proc_dry_run_no_match(self):
        # Dry run with non-existent process
        result = kill_proc(name='nonexistent_process_xyz_123', dry_run=True)
        assert result is False

    def test_kill_proc_dry_run_with_version(self):
        # Dry run with version but no match
        result = kill_proc(name='python', version='nonexistent_version_xyz', dry_run=True)
        assert result is False

    def test_kill_proc_no_match(self):
        # Non-dry run with no matching processes
        result = kill_proc(name='nonexistent_process_xyz_123_456')
        assert result is False

    def test_kill_proc_dry_run_match(self):
        # Dry run with matching process - should return True without killing
        # Using current python process name which is definitely running
        proc_name = psutil.Process().name()
        result = kill_proc(name=proc_name, dry_run=True)
        assert result is True


if __name__ == '__main__':
    pytest.main([__file__])
