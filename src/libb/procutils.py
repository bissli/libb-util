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
    proc = [p for p in psutil.process_iter() if p.name()==name]
    for p in proc:
        for c in p.connections():
            if c.status == 'LISTEN':
                yield p


def process_by_name_and_port(name, port):
    proc = [p for p in psutil.process_iter() if p.name() == name]
    for p in proc:
        for c in p.connections():
            if c.status == 'LISTEN' and c.laddr.port == port:
                return p


def kill_proc(name=None, version=None, dry_run=False, use_terminate=False):
    """Generic kill process utilitiy
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
