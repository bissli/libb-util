import datetime
import ftplib
import logging
import re
import socket
import stat
import time
from collections import namedtuple

logger = logging.getLogger('job')

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
    import sys

    from libb import log

    if len(sys.argv) != 2:
        print('usage: ftp config (e.g. site.FOO, site.BAR)')
        sys.exit(1)
    log.configure_logging()
    cn = connect(sys.argv[1])
    files = cn.dir()
    print(('\n'.join(map(repr, files))))
