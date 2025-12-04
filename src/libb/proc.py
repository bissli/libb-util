import logging
import re
from contextlib import suppress

import psutil

logger = logging.getLogger(__name__)

__all__ = [
    'process_by_name',
    'process_by_name_and_port',
    'kill_proc',
    ]


def process_by_name(name):
    """Find processes by name that are listening on a port.

    :param str name: Process name to search for.
    :yields: psutil.Process objects matching the name with LISTEN connections.

    .. seealso::
        See ``tests/test_proc.py`` for usage examples.
    """
    for p in psutil.process_iter():
        try:
            if p.name() != name:
                continue
            for c in p.connections():
                if c.status == 'LISTEN':
                    yield p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def process_by_name_and_port(name, port):
    """Find a process by name listening on a specific port.

    :param str name: Process name to search for.
    :param int port: Port number to match.
    :returns: psutil.Process if found, None otherwise.

    .. seealso::
        See ``tests/test_proc.py`` for usage examples.
    """
    for p in psutil.process_iter():
        try:
            if p.name() != name:
                continue
            for c in p.connections():
                if c.status == 'LISTEN' and c.laddr.port == port:
                    return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def kill_proc(name=None, version=None, dry_run=False, use_terminate=False):
    """Kill processes matching name and/or version.

    :param str name: Process name pattern (regex).
    :param str version: Version string to match in command line.
    :param bool dry_run: If True, just check for matches without killing.
    :param bool use_terminate: If True, use terminate instead of kill.
    :returns: True if matching processes were found.
    :rtype: bool

    .. seealso::
        See ``tests/test_proc.py`` for usage examples.
    """
    assert name or version, 'Need something to kill'
    _name = fr'.*{(name or "")}(\.exe)?$'
    match = False
    procs = []
    for proc in psutil.process_iter(attrs=['name']):
        try:
            cmd = ''.join(proc.cmdline())
        except:
            continue
        if _name and not re.match(_name, proc.name()):
            continue
        if version and version not in cmd:
            continue
        match = True
        if dry_run:
            return match
        procs.append(proc)
    gone, alive = psutil.wait_procs(procs, timeout=10)
    for p in alive:
        with suppress(Exception):
            if use_terminate:
                p.terminate()
            else:
                p.kill()
    return match
