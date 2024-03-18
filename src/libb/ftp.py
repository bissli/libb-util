import contextlib
import ftplib
import logging
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
from collections import defaultdict, namedtuple
from pathlib import Path

from libb.date import now, to_datetime

logger = logging.getLogger(__name__)

with contextlib.suppress(ImportError):
    import paramiko

__all__ = [
    'connect',
    'decrypt_all_pgp_files',
    'sync_site',
    ]

Entry = namedtuple('Entry', 'line name is_dir size datetime')
FTP_DIR_RE = (
    # typical dir entry
    # drwxr-xr-x 2   4100            4100    4096    Sep 07 17:54 incoming
    # drwxr-xr-x 2   4100            4100    237568  Sep 08 10:42 outgoing
    # -rw-r--r-- 1   4100            4100    29948   Sep 07 22:35 foobarbaz.txt.pgp.20000907
    r'([drwx-]+)\s+\d+\s+\w+\s+\w+\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.*)\s*$',
    # alternate that leaves out one field
    # drwxrwx--x   3 500         2048 Sep  7 19:00 incoming
    # drwxr-xr-x   2 400         1024 Sep  8 09:29 outgoing
    # -rw-r--r--   1 500        19045 Sep  7 06:10 20000907.FOO.BAR_BAZ.csv.asc
    r'([drwx-]+)\s+\d+\s+\w+\s+(\d+)\s+(\w+\s+\d+\s+[\d:]+)\s+(.*)\s*$',
)


def connect(sitename, directory=None, config=None):
    """Connect to a site using a sitename configuration
    return the FTP object else raise exception
    having trouble with SSL auth?  test with ossl command:
    openssl s_client -starttls ftp -connect host.name:port

    Create a config module with Setting configs. Add in each ste that
    needs to be synced.

    `sitename` params:
    -----------------

    - required:
    `hostname`
    `username`
    `password`

    - optional:
    `secure`
    `is_encrypted`
    `rename_gpg`
    `pgp_extension`
    `localdir`
    `ignore_re`

    """
    this = config
    for level in sitename.split('.'):
        this = getattr(this, level)
    site = this.ftp
    tries, cn = 0, None
    while tries < 10 and not cn:
        try:
            if site.get('secure', False):
                cn = SecureFtpConnection(site.hostname, username=site.username,
                                         password=site.password,
                                         port=site.get('port', 22))
                if not cn:
                    raise paramiko.SSHException
            else:
                cn = FtpConnection(site.hostname, site.username, site.password)
        except (paramiko.SSHException, socket.error) as err:
            logger.error(err)
            time.sleep(10)
            tries += 1
    if not cn or tries > 10:
        return
    if directory:
        cn.cd(directory)
    return cn


def parse_ftp_dir_entry(line, tzinfo):
    for pattern in FTP_DIR_RE:
        if m := re.search(pattern, line):
            try:
                return Entry(line, m.group(4), m.group(1)[0] == 'd',
                             int(m.group(2)),
                             to_datetime(m.group(3)).replace(tzinfo=tzinfo))
            except Exception as exc:
                logger.error(f'Error with line {line}, groups: {m.groups()}')
                logger.exception(exc)
                raise exc


def sync_site(sitename, opts, config):
    """Use local config module to specify sites to sync via FTP

    Assumes that local config.py contains a general stie structure
    for vendors:

    `local config.py`

    vendors = Setting()

    vendors.foo.ftp.hostname = 'sftp.foovendor.com'
    vendors.foo.ftp.username = 'foouser'
    vendors.foo.ftp.password = 'foopasswd'
    ...
    vendors.bar.ftp.hostname = 'sftp.barvendor.com'
    vendors.bar.ftp.username = 'baruser'
    vendors.bar.ftp.password = 'barpasswd'
    ...

    opts:
        `nocopy`: do not copy anything
        `nodecryptlocal`: do not decrypt local files
        `ignorelocal`: ignore presence of local file when deciding to copy
        `ignoresize`: ignore size of local file when deciding to copy
        `ignoreolderthan`: ignore files older than number of days
        `address`: Send notification of new files to address

    """
    logger.info(f'Syncing FTP site for {sitename}')
    files = []
    if cn := connect(sitename, '.', config):
        this = config
        for level in sitename.split('.'):
            this = getattr(this, level)
        site = this.ftp
        opts.is_encrypted = site.get('is_encrypted', is_encrypted)
        opts.rename_pgp = site.get('rename_pgp', rename_pgp)
        opts.pgp_extension = site.get('pgp_extension')
        opts.stats = defaultdict(int)
        opts.ignore_re = site.get('ignore_re', None)
        sync_directory(cn, site, '/', Path(site.localdir), files, opts)
        logger.info(
            '%d copied, %d decrypted, %d skipped, %d ignored',
            opts.stats['copied'],
            opts.stats['decrypted'],
            opts.stats['skipped'],
            opts.stats['ignored'],
        )
    return files


def sync_directory(cn, site, remotedir: str, localdir: Path, files, opts):
    """Sync a remote FTP directory to a local directory recursively
    """
    logger.info(f'Syncing directory {remotedir}')
    wd = cn.pwd()
    try:
        logger.debug(f'CD down to: {remotedir}')
        cn.cd(remotedir)
        entries = cn.dir()
        for entry in entries:
            if opts.ignore_re and re.match(opts.ignore_re, entry.name):
                logger.debug(f'Ignoring file that matches ignore pattern: {entry.name}')
                opts.stats['ignored'] += 1
                continue
            if entry.is_dir:
                sync_directory(cn, site, (Path(remotedir) / entry.name).as_posix(),
                               localdir / entry.name, files, opts)
                continue
            try:
                filename = sync_file(cn, site, remotedir, localdir, entry, opts)
                if filename:
                    files.append(filename)
            except:
                logger.exception('Error syncing file: %s/%s', remotedir, entry.name)
    finally:
        logger.debug(f'CD back to {wd}')
        cn.cd(wd)


def sync_file(cn, site, remotedir: str, localdir: Path, entry, opts):
    if opts.ignoreolderthan and entry.datetime < pendulum.now().subtract(days=int(opts.ignoreolderthan)):
        logger.debug('File is too old: %s/%s, skipping (%s)', remotedir, entry.name, str(entry.datetime))
        return
    localfile = localdir / entry.name
    localpgpfile = (localdir / '.pgp') / entry.name
    if not opts.ignorelocal and (localfile.exists() or localpgpfile.exists()):
        st = localfile.stat() if localfile.exists() else localpgpfile.stat()
        if entry.datetime <= to_datetime(st.st_mtime):
            if not opts.ignoresize and (entry.size == st.st_size):
                logger.debug('File has not changed: %s/%s, skipping', remotedir, entry.name)
                opts.stats['skipped'] += 1
                return
    logger.debug('Downloading file: %s/%s to %s', remotedir, entry.name, localfile)
    filename = None
    with contextlib.suppress(Exception):
        Path(os.path.split(localfile)[0]).mkdir(parents=True)
    if not opts.nocopy:
        cn.getbinary(entry.name, localfile)
        mtime = time.mktime(entry.datetime.timetuple())
        try:
            os.utime(localfile, (mtime, mtime))
        except OSError:
            logger.warning(f'Could not touch new file time on {localfile}')
        opts.stats['copied'] += 1
        filename = localfile
    if not opts.nocopy and not opts.nodecryptlocal and opts.is_encrypted(localfile.as_posix()):
        newname = opts.rename_pgp(entry.name)
        # keep a copy for stat comparison above but move to .pgp dir so it doesn't clutter the main directory
        decrypt_pgp_file(localdir, entry.name, newname, opts.pgp_extension)
        with contextlib.suppress(Exception):
            os.makedirs(os.path.split(localpgpfile)[0])
        shutil.move(localfile, localpgpfile)
        opts.stats['decrypted'] += 1
        filename = localdir / newname
    return filename


def is_encrypted(filename: str):
    return 'pgp' in filename.split('.')


def rename_pgp(pgpname: str):
    bits = pgpname.split('.')
    bits.remove('pgp')
    return '.'.join(bits)


def decrypt_pgp_file(path: Path, pgpname: str, newname=None, load_extension=None):
    """Decrypt file with GnuPG: FIXME move this to a library
    """
    if not newname:
        newname = rename_pgp(pgpname)
    if newname == pgpname:
        raise ValueError('pgpname and newname cannot be the same')
    logger.debug(f'Decrypting file {pgpname} to {newname}')
    from libb import config
    gpg_cmd = [
        config.gpg.exe,
        '--homedir',
        config.gpg.dir,
        '--decrypt',
        '--batch',
        '--yes',
        '--passphrase-fd',
        '0',
        '--output',
        (path / newname).as_posix(),
        '--decrypt',
        (path / pgpname).as_posix(),
    ]
    if load_extension:
        gpg_cmd.insert(-3, '--load-extension')
        gpg_cmd.insert(-3, load_extension)
    logger.debug(' '.join(gpg_cmd))
    p = subprocess.Popen(gpg_cmd, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True)
    out, err = p.communicate('password')
    if 'gpg: decryption failed: secret key not available' in err:
        logger.error('Failed to decrypt %s\n%s:', pgpname, err)
    if 'decrypt_message failed: file open error' in err:
        logger.error('Failed to decrypt %s\n%s:', pgpname, err)


def decrypt_all_pgp_files(config, sitename, opts):
    """Backup approach to decrypting all saved pgp files

    Assumes that local config.py contains a general stie structure
    for vendors:

    `local config.py`

    vendors = Setting()

    vendors.foo.ftp.hostname = 'sftp.foovendor.com'
    vendors.foo.ftp.username = 'foouser'
    vendors.foo.ftp.password = 'foopasswd'
    ...
    vendors.bar.ftp.hostname = 'sftp.barvendor.com'
    vendors.bar.ftp.username = 'baruser'
    vendors.bar.ftp.password = 'barpasswd'
    ...
    """
    this = config
    for level in sitename.split('.'):
        this = getattr(this, level)
    site = this.ftp
    is_encrypted_fn = site.get('is_encrypted', is_encrypted)
    rename_pgp_fn = site.get('rename_pgp', rename_pgp)
    pgp_extension = site.get('pgp_extension')
    files = []
    for localdir, _, files in os.walk(site.localdir):
        if '.pgp' in os.path.split(localdir):
            continue
        localdir = Path(localdir)
        logger.info(f'Walking through {len(files)} files')
        for name in files:
            localfile = localdir / name
            localpgpfile = (localdir / '.pgp') / name
            if opts.ignoreolderthan:
                created_on = to_datetime(localfile.stat().st_ctime)
                ignore_datetime = now().subtract(days=int(opts.ignoreolderthan))
                if created_on < ignore_datetime:
                    logger.debug('File is too old: %s/%s, skipping (%s)',
                                 localdir, name, str(created_on))
                    continue
            if is_encrypted_fn(name):
                newname = rename_pgp_fn(name)
                decrypt_pgp_file(localdir, name, newname, pgp_extension)
                with contextlib.suppress(Exception):
                    os.makedirs(os.path.split(localpgpfile)[0])
                shutil.move(localfile, localpgpfile)
                filename = localdir / newname
                files.append(filename)
    return files


class FtpConnection:
    """Wrapper around ftplib
    """
    def __init__(self, hostname, username, password, **kw):
        self.ftp = ftplib.FTP(hostname, username, password)
        self._tzinfo = kw.get('tzinfo', LCL)

    def pwd(self):
        """Return the current directory"""
        return self.ftp.pwd()

    def cd(self, path):
        """Change the working directory"""
        return self.ftp.cwd(path)

    def dir(self):
        """Return a directory listing as an array of lines"""
        lines = []
        self.ftp.dir(lines.append)
        entries = []
        for line in lines:
            entry = parse_ftp_dir_entry(line, self._tzinfo)
            if entry:
                entries.append(entry)
        return entries

    def files(self):
        """Return a bare filename listing as an array of strings"""
        return self.ftp.nlst()

    def getascii(self, remotefile, localfile=None):
        """Get a file in ASCII (text) mode"""
        with open(localfile or remotefile, 'w') as f:
            self.ftp.retrlines(f'RETR {remotefile}', lambda line: f.write(line + '\n'))

    def getbinary(self, remotefile, localfile=None):
        """Get a file in binary mode"""
        with open(localfile or remotefile, 'wb') as f:
            self.ftp.retrbinary(f'RETR {remotefile}', f.write)

    def putascii(self, localfile, remotefile=None):
        """Put a file in ASCII (text) mode"""
        with open(localfile, 'rb') as f:
            self.ftp.storlines(f'STOR {remotefile or localfile}', f)

    def putbinary(self, localfile, remotefile=None):
        """Put a file in binary mode"""
        with open(localfile, 'rb') as f:
            self.ftp.storbinary(f'STOR {remotefile or localfile}', f, 1024)

    def delete(self, remotefile):
        self.ftp.delete(remotefile)

    def close(self):
        with contextlib.suppress(Exception):
            self.ftp.close()


class SecureFtpConnection:
    def __init__(self, hostname, username, password, port=22, **kw):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname,
            username=username,
            password=password,
            port=port,
            allow_agent=kw.get('allow_agent', False),
            look_for_keys=kw.get('look_for_keys', False),
        )
        self.ftp = self.ssh.open_sftp()
        self._tzinfo = kw.get('tzinfo', LCL)

    def pwd(self):
        """Return the current directory"""
        return self.ftp.getcwd()

    def cd(self, path):
        """Change the working directory"""
        return self.ftp.chdir(path)

    def dir(self):
        """Return a directory listing as an array of lines"""
        files = self.ftp.listdir_attr()
        entries = []
        for f in files:
            entry = Entry(f.longname, f.filename, stat.S_ISDIR(f.st_mode),
                          f.st_size,
                          to_datetime(f.st_mtime).replace(tzinfo=self._tzinfo))
            entries.append(entry)
        return entries

    def files(self):
        """Return a bare filename listing as an array of strings"""
        return self.ftp.listdir()

    def getascii(self, remotefile, localfile=None):
        """Get a file in ASCII (text) mode"""
        self.ftp.get(remotefile, localfile or remotefile)

    def getbinary(self, remotefile, localfile=None):
        """Get a file in binary mode"""
        try:
            self.ftp.get(remotefile, localfile or remotefile)
        except EnvironmentError:
            logger.warning(f'Could not GET {remotefile}')

    def putascii(self, localfile, remotefile=None):
        """Put a file in ASCII (text) mode"""
        self.ftp.put(localfile, remotefile or localfile)

    def putbinary(self, localfile, remotefile=None):
        """Put a file in binary mode"""
        self.ftp.put(localfile, remotefile or localfile)

    def delete(self, remotefile):
        self.ftp.remove(remotefile)

    def close(self):
        with contextlib.suppress(Exception):
            self.ftp.close()
            self.ssh.close()


class SslFtpConnection:
    """Placeholder FTP connection for sites that use SSL"""

    def __init__(self):
        raise NotImplementedError


if __name__ == '__main__':
    from libb.log import configure_logging

    if len(sys.argv) != 2:
        print('usage: ftp config (e.g. site.FOO, site.BAR)')
        sys.exit(1)
    configure_logging()
    cn = connect(sys.argv[1])
    files = cn.dir()
    print(('\n'.join(map(repr, files))))
