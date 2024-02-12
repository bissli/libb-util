import contextlib
import datetime
import ftplib
import logging
import os
import posixpath
import re
import shutil
import socket
import stat
import subprocess
import sys
import time
from collections import defaultdict, namedtuple

logger = logging.getLogger(__name__)

import paramiko

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
    """Connect to a site using a vendor configuration
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
        return None
    if directory:
        cn.cd(directory)
    return cn


def parse_ftp_dir_entry(line):
    def to_datetime(s):
        # Format: Sep 27 17:11
        if m := re.search(r'([A-Za-z]{3})\s+(\d{1,2})\s+(\d{1,2}):(\d{2})', s):
            # No year, so we need to stuff in the current year
            s = '%d %s' % (datetime.date.today().year, s)
            try:
                tm = list(time.strptime(s, '%Y %b %d %H:%M')[:6])
            except ValueError as e:
                logger.info(s)
                raise e
            tm[0] = datetime.date.today().year
            return datetime.datetime(*tm)
        # Format: Jan 29  2010
        if m := re.search(r'([A-Za-z]{3})\s+(\d{1,2})\s+(\d{4})', s):
            # No time, leave default of 12:00
            tm = time.strptime(s, '%b %d %Y')[:6]
            return datetime.datetime(*tm)
        raise ValueError('Unhandled date/time format: %s', s)

    for pattern in FTP_DIR_RE:
        if m := re.search(pattern, line):
            try:
                return Entry(line, m.group(4), m.group(1)[0] == 'd', int(m.group(2)), to_datetime(m.group(3)))
            except Exception as exc:
                logger.error(f'Error with line {line}, groups: {m.groups()}')
                logger.exception(exc)
                raise exc
    return None


def sync_site(vendor, opts, config, notify=False):
    """Use local config module to specify sites to sync via FTP

    opts:
        `nocopy`: do not copy anything
        `nodecryptlocal`: do not decrypt local files
        `ignorelocal`: ignore presence of local file when deciding to copy
        `ignoresize`: ignore size of local file when deciding to copy
        `ignoreolderthan`: ignore files older than number of days
        `address`: Send notification of new files to address

    """
    logger.info(f'Syncing FTP site for {vendor}')
    files = []
    cn = connect(vendor, '.', config)
    if cn:
        this = config
        for level in vendor.split('.'):
            this = getattr(this, level)
        site = this.ftp
        opts.is_encrypted = site.get('is_encrypted', is_encrypted)
        opts.rename_pgp = site.get('rename_pgp', rename_pgp)
        opts.pgp_extension = site.get('pgp_extension')
        opts.stats = defaultdict(int)
        opts.ignore_re = site.get('ignore_re', None)
        sync_directory(cn, site, '/', site.localdir, files, opts)
        logger.info(
            '%d copied, %d decrypted, %d skipped, %d ignored',
            opts.stats['copied'],
            opts.stats['decrypted'],
            opts.stats['skipped'],
            opts.stats['ignored'],
        )
    if notify and files and opts.address:
        send_mail(site, files, opts.address, config)
    return files


def sync_directory(cn, site, remotedir, localdir, files, opts):
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
                sync_directory(
                    cn, site, posixpath.join(remotedir, entry.name),
                    posixpath.join(localdir, entry.name), files, opts
                )
            else:
                try:
                    filename = sync_file(cn, site, remotedir, localdir, entry, opts)
                    if filename:
                        files.append(filename)
                except:
                    logger.exception('Error syncing file: %s/%s', remotedir, entry.name)
    finally:
        logger.debug('CD back to: ' + wd)
        cn.cd(wd)


def sync_file(cn, site, remotedir, localdir, entry, opts):
    if opts.ignoreolderthan:
        ignore_datetime = datetime.datetime.now() - datetime.timedelta(int(opts.ignoreolderthan))
        if entry.datetime < ignore_datetime:
            logger.debug('File is too old: %s/%s, skipping (%s)', remotedir, entry.name, str(entry.datetime))
            return None
    localfile = posixpath.join(localdir, entry.name)
    localpgpfile = posixpath.join(localdir, '.pgp', entry.name)
    if not opts.ignorelocal and (os.path.exists(localfile) or os.path.exists(localpgpfile)):
        st = os.stat(localfile) if os.path.exists(localfile) else os.stat(localpgpfile)
        if entry.datetime <= datetime.datetime.fromtimestamp(st.st_mtime):
            if not opts.ignoresize and (entry.size == st.st_size):
                logger.debug('File has not changed: %s/%s, skipping', remotedir, entry.name)
                opts.stats['skipped'] += 1
                return None
    logger.debug('Downloading file: %s/%s to %s', remotedir, entry.name, localfile)
    filename = None
    with contextlib.suppress(Exception):
        os.makedirs(os.path.split(localfile)[0])
    if not opts.nocopy:
        cn.getbinary(entry.name, localfile)
        mtime = time.mktime(entry.datetime.timetuple())
        try:
            os.utime(localfile, (mtime, mtime))
        except OSError:
            logger.warning(f'Could not touch new file time on {localfile}')
        opts.stats['copied'] += 1
        filename = localfile
    if not opts.nocopy and not opts.nodecryptlocal and opts.is_encrypted(localfile):
        newname = opts.rename_pgp(entry.name)
        # keep a copy for stat comparison above but move to .pgp dir so it doesn't clutter the main directory
        decrypt_pgp_file(localdir, entry.name, newname, opts.pgp_extension)
        with contextlib.suppress(Exception):
            os.makedirs(os.path.split(localpgpfile)[0])
        shutil.move(localfile, localpgpfile)
        opts.stats['decrypted'] += 1
        filename = posixpath.join(localdir, newname)
    return filename


def is_encrypted(filename):
    return 'pgp' in filename.split('.')


def rename_pgp(pgpname):
    bits = pgpname.split('.')
    bits.remove('pgp')
    return '.'.join(bits)


def decrypt_pgp_file(path, pgpname, newname=None, load_extension=None):
    """Decrypt file with GnuPG: FIXME move this to a library"""
    if not newname:
        bits = pgpname.split('.')
        bits.remove('pgp')
        newname = '.'.join(bits)
    if newname == pgpname:
        raise ValueError('pgpname and newname cannot be the same')
    logger.debug('Decrypting file %s to %s', pgpname, newname)
    from libb import config
    gpg_cmd = [
        config.gpg.exe,
        '--homedir',
        config.gpg.home,
        '--decrypt',
        '--batch',
        '--yes',
        '--passphrase-fd',
        '0',
        '--output',
        posixpath.join(path, newname),
        posixpath.join(path, pgpname),
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


def send_mail(vendor, files, address, config):
    from libb import mail
    this = config
    for level in vendor.split('.'):
        this = getattr(this, level)
    subject = 'New files downloaded from: ' + this.get('name', libb.splitcap(vendor, delim='.'))
    # get the common parent path - need to split it so if there is one file
    # it won't return the actual file name
    path = os.path.commonprefix([os.path.split(_)[0] for _ in files])
    path = path.replace('/', '\\')
    msg = [subject, '', f'Parent folder: <a href="{path}">{path}</a>', '']
    msg.extend(files)
    html = '<html><body><pre>\n' + '\n'.join(msg) + '\n</pre></body></html>'
    mail.send_mail(address.split(','), subject, html, subtype='html')


class FtpConnection:
    def __init__(self, hostname, username, password):
        self.ftp = ftplib.FTP(hostname, username, password)

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
            entry = parse_ftp_dir_entry(line)
            if entry:
                entries.append(entry)
        return entries

    def files(self):
        """Return a bare filename listing as an array of strings"""
        return self.ftp.nlst()

    def getascii(self, remotefile, localfile=None):
        """Get a file in ASCII (text) mode"""
        outf = open(localfile or remotefile, 'w', encoding='locale')
        try:
            self.ftp.retrlines('RETR ' + remotefile, lambda line: outf.write(line + '\n'))
        finally:
            outf.close()

    def getbinary(self, remotefile, localfile=None):
        """Get a file in binary mode"""
        outf = open(localfile or remotefile, 'wb')
        try:
            self.ftp.retrbinary('RETR ' + remotefile, outf.write)
        finally:
            outf.close()

    def putascii(self, localfile, remotefile=None):
        """Put a file in ASCII (text) mode"""
        self.ftp.storlines('STOR ' + (remotefile or localfile), open(localfile, encoding='locale'))

    def putbinary(self, localfile, remotefile=None):
        """Put a file in binary mode"""
        self.ftp.storbinary('STOR ' + (remotefile or localfile), open(localfile, 'rb'), 1024)

    def delete(self, remotefile):
        self.ftp.delete(remotefile)

    def close(self):
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
            entry = Entry(
                f.longname,
                f.filename,
                stat.S_ISDIR(f.st_mode),
                f.st_size,
                datetime.datetime.fromtimestamp(f.st_mtime or 0),
            )
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
        self.ftp.close()
        self.ssh.close()


class SslFtpConnection:
    """Placeholder FTP connection for sites that use SSL"""

    def __init__(self):
        raise NotImplementedError


if __name__ == '__main__':
    from libb import log

    if len(sys.argv) != 2:
        print('usage: ftp config (e.g. site.FOO, site.BAR)')
        sys.exit(1)
    log.configure_logging()
    cn = connect(sys.argv[1])
    files = cn.dir()
    print(('\n'.join(map(repr, files))))
