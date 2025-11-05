"""Windows Utilities"""

import logging
import os
import platform
import socket
from subprocess import PIPE, Popen

import regex as re

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

if 'Win' in platform.system():
    from win32com.client import GetObject


def run_command(cmd, workingdir=None, raise_on_error=True, hidearg=None):
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
        curdir = os.getcwd()
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
        elif err:
            logger.info(err)
        return out + err
    finally:
        if workingdir:
            os.chdir(curdir)


class psexec_session:
    """Context manager for running psexec commands. These
    require the admin share to be mounted. Usage:

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
    """Context manager for temporarily mounting a share so can
    run commands against a remote server's file system. Usage:

        with shell.file_share_session(host, password):
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
    """Mount the admin share which is required to run psexec commands.

    This is necessary before running psexec commands because it
    uses the admin$ share on the remote host. I've had problems where
    Windows complains about multiple connections to a share by the
    same user using more than one user name, but if you connect
    by IP address, it seems to work around this. So I resolve the
    host to IP first and connect that way.
    """
    user = os.environ['USERNAME'].lower()
    hostip = socket.gethostbyname(host)
    if not unmount:
        run_command(['net', 'use', r'\\' + hostip + r'\admin$', r'/user:TENOR\%s' % user, password], hidearg=password)
    else:
        run_command(['net', 'use', r'\\' + hostip + r'\admin$', '/del'])


def mount_file_share(host, password, drive, share, unmount=False):
    """Mount a file share."""
    user = os.environ['USERNAME'].lower()
    hostip = socket.gethostbyname(host)
    if not unmount:
        run_command(
            ['net', 'use', drive, r'\\' + hostip + '\\' + share, r'/user:TENOR\%s' % user, password], hidearg=password
        )
    else:
        run_command(['net', 'use', drive, '/del'])


def parse_wmic_output(output):
    """Parse output from WMIC query

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
    WMI = GetObject('winmgmts:')
    processes = WMI.InstancesOf('Win32_Process')
    for p in WMI.ExecQuery('select * from Win32_Process where Name="cmd.exe"'):
        logger.debug('Killing PID:', p.Properties_('ProcessId').Value)
        os.system('taskkill /pid ' + str(p.Properties_('ProcessId').Value))


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
