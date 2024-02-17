import contextlib
import os
import struct

import config
import pytest
from libb import ftp


def make_text_file(filename, lines):
    with open(filename, 'w') as f:
        for i in range(lines):
            f.write('Line %d\n' % i)


def make_binary_file(filename, ints):
    with open(filename, 'wb') as f:
        for i in range(ints):
            n = struct.pack('i', i)
            f.write(n)


def test_ftp_pub_ascii(ftp_docker):
    localfile = os.path.join(config.tmpdir.dir, 'Local.txt')
    make_text_file(localfile, 10)
    ftpcn = ftp.connect('vendor.FOO', config=config)
    with contextlib.suppress(Exception):
        ftpcn.delete('Remote.txt')
    ftpcn.putascii(localfile, 'Remote.txt')
    files = ftpcn.files()
    assert 'Remote.txt' in files
    remotefile = os.path.join(config.tmpdir.dir, 'Remote.txt')
    ftpcn.getascii('Remote.txt', remotefile)
    assert open(localfile, 'r').read() == open(remotefile, 'r').read()
    ftpcn.delete('Remote.txt')
    ftpcn.close()


def test_put_get_binary(ftp_docker):
    localfile = os.path.join(config.tmpdir.dir, 'Local.dat')
    make_binary_file(localfile, 1000)
    ftpcn = ftp.connect('vendor.FOO', config=config)
    with contextlib.suppress(Exception):
        ftpcn.delete('Remote.dat')
    ftpcn.putbinary(localfile, 'Remote.dat')
    files = ftpcn.files()
    assert 'Remote.dat' in files
    remotefile = os.path.join(config.tmpdir.dir, 'Remote.dat')
    ftpcn.getbinary('Remote.dat', remotefile)
    assert open(localfile, 'rb').read() == open(remotefile, 'rb').read()
    ftpcn.delete('Remote.dat')
    ftpcn.close()


if __name__ == '__main__':
    pytest.main([__file__])
