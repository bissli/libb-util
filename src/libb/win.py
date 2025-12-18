"""Windows Utilities"""

import logging
import os
import platform
import socket
from subprocess import PIPE, Popen

import regex as re
import pathlib

logger = logging.getLogger(__name__)

__all__ = [
    'run_command',
    'psexec_session',
    'file_share_session',
    'mount_admin_share',
    'mount_file_share',
    'parse_wmic_output',
    'exit_cmd',
]

_HAS_WIN32COM = False
if 'Win' in platform.system():
    try:
        from win32com.client import GetObject
        _HAS_WIN32COM = True
    except ImportError:
        pass


def run_command(cmd, workingdir=None, raise_on_error=True, hidearg=None):
    """Execute a shell command and return output.

    :param cmd: Command as string or list of arguments.
    :param str workingdir: Directory to execute in (optional).
    :param bool raise_on_error: Raise exception on non-zero return code.
    :param str hidearg: Argument value to mask in logs (for passwords).
    :returns: Combined stdout and stderr output.
    :rtype: bytes
    :raises Exception: If command fails and raise_on_error is True.

    .. seealso::
        See ``tests/test_win.py`` for usage examples.
    """
    def hide(cmd):
        for bit in cmd:
            if bit == hidearg:
                yield '******'
            else:
                yield bit

    if not isinstance(cmd, (list, tuple)):
        cmd = cmd.split(' ')

    logger.info(f"Running: {' '.join(hide(cmd))}")
    if workingdir:
        curdir = pathlib.Path.cwd()
        os.chdir(workingdir)

    try:
        p = Popen(cmd, stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        if out:
            logger.info(out)
        if p.returncode != 0 and raise_on_error:
            msg = f"Error executing: {' '.join(hide(cmd))}"
            if workingdir:
                msg += f' in {workingdir}'
            logger.error(msg)
            raise Exception(err)
        if err:
            logger.info(err)
        return out + err
    finally:
        if workingdir:
            os.chdir(curdir)


class psexec_session:
    """Context manager for running psexec commands.

    Mounts admin share before commands and unmounts on exit.

    :param str host: Remote host name or IP.
    :param str password: Password for authentication.

    Example::

        with shell.psexec_session(host, password):
            for cmd in commands:
                out = shell.run_command(cmd)
    """

    def __init__(self, host, password):
        self.host = host
        self.password = password

    def __enter__(self):
        mount_admin_share(self.host, self.password)

    def __exit__(self, type, value, traceback):
        mount_admin_share(self.host, self.password, unmount=True)


class file_share_session:
    """Context manager for temporarily mounting a file share.

    Mounts share before commands and unmounts on exit.

    :param str host: Remote host name or IP.
    :param str password: Password for authentication.
    :param str drive: Local drive letter to mount to.
    :param str share: Remote share name.

    Example::

        with shell.file_share_session(host, password, 'Z:', 'data'):
            for cmd in commands:
                out = shell.run_command(cmd)
    """

    def __init__(self, host, password, drive, share):
        self.host = host
        self.password = password
        self.drive = drive
        self.share = share

    def __enter__(self):
        mount_file_share(self.host, self.password, self.drive, self.share)

    def __exit__(self, type, value, traceback):
        mount_file_share(self.host, self.password, self.drive, self.share, unmount=True)


def mount_admin_share(host, password, unmount=False):
    """Mount or unmount the admin$ share required for psexec commands.

    Resolves host to IP address to avoid Windows multiple-connection errors.

    :param str host: Remote host name.
    :param str password: Password for authentication.
    :param bool unmount: If True, unmount instead of mount.

    .. note::
        Connects by IP address to work around Windows complaining about
        multiple connections to a share by the same user.
    """
    user = os.environ['USERNAME'].lower()
    hostip = socket.gethostbyname(host)
    if not unmount:
        run_command(['net', 'use', r'\\' + hostip + r'\admin$', rf'/user:TENOR\{user}', password], hidearg=password)
    else:
        run_command(['net', 'use', r'\\' + hostip + r'\admin$', '/del'])


def mount_file_share(host, password, drive, share, unmount=False):
    """Mount or unmount a Windows file share.

    :param str host: Remote host name.
    :param str password: Password for authentication.
    :param str drive: Local drive letter to mount to.
    :param str share: Remote share name.
    :param bool unmount: If True, unmount instead of mount.
    """
    user = os.environ['USERNAME'].lower()
    hostip = socket.gethostbyname(host)
    if not unmount:
        run_command(
            ['net', 'use', drive, r'\\' + hostip + '\\' + share, rf'/user:TENOR\{user}', password], hidearg=password
        )
    else:
        run_command(['net', 'use', drive, '/del'])


def parse_wmic_output(output):
    """Parse output from WMIC query into list of dicts.

    :param str output: Raw WMIC output string.
    :returns: List of dictionaries with column headers as keys.
    :rtype: list[dict]

    Example::

        >> wmic_output = os.popen('wmic product where name="Python 2.7.11" get Caption, Description, Vendor').read()
        >> result = parse_wmic_output(wmic_output)
        >> result[0]['Caption']
        >> result[0]['Vendor']
    """
    result = []
    lines = [s for s in output.splitlines() if s.strip()]
    if len(lines) == 0:
        return result
    header_line = lines[0]
    headers = re.findall(r'\S+\s+|\S$', header_line)
    pos = [0]
    for header in headers:
        pos.append(pos[-1] + len(header))
    for i in range(len(headers)):
        headers[i] = headers[i].strip()
    for r in range(1, len(lines)):
        row = {}
        for i in range(len(pos) - 1):
            row[headers[i]] = lines[r][pos[i] : pos[i + 1]].strip()
        result.append(row)
    return result


def exit_cmd():
    """Kill all running cmd.exe processes via WMI.

    Requires pywin32 to be installed on Windows.
    """
    if not _HAS_WIN32COM:
        raise ImportError('exit_cmd requires pywin32: pip install pywin32')
    WMI = GetObject('winmgmts:')
    processes = WMI.InstancesOf('Win32_Process')
    for p in WMI.ExecQuery('select * from Win32_Process where Name="cmd.exe"'):
        logger.debug(f'Killing PID: {p.Properties_("ProcessId").Value}')
        os.system('taskkill /pid ' + str(p.Properties_('ProcessId').Value))


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
