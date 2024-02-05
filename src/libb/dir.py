"""os.walk and even scandir are miserably slow over network connections in Python 2.
Once you migrate to Python 3, move off glob match to full regex match.
"""
import errno
import glob
import itertools
import logging
import os
import posixpath
import random
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import (  # noqa
    Path,
    PosixPath,
    PurePath,
    PurePosixPath,
    PureWindowsPath,
    WindowsPath,
)

import regex as re

logger = logging.getLogger(__name__)


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise


@contextmanager
def make_tmpdir(prefix=None):
    """Context manager to wrap a temporary directory with auto-cleanup

    >>> import os.path
    >>> fpath = ""
    >>> with make_tmpdir() as basedir:
    ...     fpath = os.path.join(basedir, 'temp.txt')
    ...     with open(fpath, "w") as file:
    ...         file.write("We expect the file to be deleted when context closes")
    52
    >>> try:
    ...     file = open(fpath, "w")
    ... except IOError as io:
    ...     raise Exception('File does not exist')
    Traceback (most recent call last):
    ...
    Exception: File does not exist
    """
    prefix = prefix or tempfile.gettempdir()
    prefix = os.path.join(prefix, '')
    path = tempfile.mkdtemp(prefix=prefix)
    try:
        yield path
    finally:
        try:
            shutil.rmtree(path)
        except IOError as io:
            logger.error(f'Failed to clean up temp dir {path}')


def safe_move(source, target, hard_remove=False):
    """Move a file to a new location, optionally deleting anything in the way"""
    if hard_remove:
        if not os.path.exists(target):
            logger.info(f'There is no file to remove at target: {target}')
        else:
            os.remove(target)
            logger.info(f'Removed file at target location: {target}')
    try:
        shutil.move(source, target)
    except EnvironmentError as err:
        logger.warning('Target already used; adding rendom string to target loc, trying again.')
        targetname, ext = os.path.splitext(target)
        targetname += bytes(random.getrandbits(128))
        target = targetname + ext
        shutil.move(source, target)
        logger.warning(f'Succeeded moving to new target: {target}')
    return target


def _append_date(pattern, thedate):
    """Replace date in glob directory match function

    >>> import datetime
    >>> _append_date("{:%Y%m%d}_Foobar.txt", datetime.date(2018,1,1))
    '20180101_Foobar.txt'
    >>> _append_date("Foobar*.txt", datetime.date(2018,1,1))
    'Foobar*_20180101.txt'
    >>> _append_date("Foobar", datetime.date(2018,1,1))
    'Foobar_20180101'
    """
    match = re.search(r':%Y%m%d', pattern)
    if match:
        return pattern.format(thedate)
    match = re.search(r'\.', pattern)
    if match:
        ix = match.start()
        pattern = pattern[:ix] + f'_{thedate:%Y%m%d}' + pattern[ix:]
    else:
        pattern += f'_{thedate:%Y%m%d}'
    return pattern


def save_file_tmpdir(fname, content, thedate=None, **kw):
    """Save a document to the specified temp directory, save with date

    >>> import datetime
    >>> content = "</html>...</html>"
    >>> save_file_tmpdir("Foobar.txt", content, thedate=datetime.date.today())
    """
    tmpdir = kw.pop('tmpdir', tempfile.gettempdir())
    if thedate:
        fname = _append_date(fname, thedate)
    pathname = os.path.join(tmpdir, fname)
    with open(pathname, 'w', encoding='locale') as f:
        f.write(content)
        logger.info(f'Tmp saved {pathname} {fname}')


def get_dir_match(dir_pattern, thedate=None):
    """Get path of existing files matching each `glob` pattern, filter zero sizes,
    return warnings
    """
    results = []
    warnings = []
    for directory, pattern in dir_pattern:
        if thedate:
            pattern = _append_date(pattern, thedate)
        glob_pattern = os.path.join(directory, pattern)
        files = glob.glob(glob_pattern)
        if files:
            for fpath in files:
                if os.stat(fpath).st_size == 0:
                    themsg = f'Skipping zero-length file: {fpath}'
                    warnings.append(themsg)
                    logger.warning(themsg)
                    continue
                results.append(fpath)
        else:
            themsg = f'{glob_pattern} NOT FOUND'
            warnings.append(themsg)
            logger.warning(themsg)
    return results, warnings


def load_files(directory, pattern='*', thedate=None):
    files, _ = get_dir_match([(directory, pattern)], thedate)
    logger.info(f'Found {len(files)} matching files in {directory}')
    for pathname in files:
        try:
            with open(pathname, 'r', encoding='locale') as f:
                _file = f.read()
            yield _file
        except:
            logger.error(f'{pathname} no longer available...')


def load_files_tmpdir(patterns='*', thedate=None):
    """Get document from temp local store by identifier and date

    >>> import datetime
    >>> patterns = ("Fooba*.txt", "Fooba*.txt",)
    >>> results = load_files_tmpdir(patterns, datetime.date.today())
    >>> next(results, None)
    '</html>...</html>'
    >>> next(results, None)
    '</html>...</html>'
    >>> next(results)
    Traceback (most recent call last):
    ...
    StopIteration
    """
    tmpdir = tempfile.gettempdir()
    if not isinstance(patterns, (list, tuple)):
        patterns = (patterns,)
    gen = []
    for pattern in patterns:
        gen.append(load_files(tmpdir, pattern, thedate))
    return itertools.chain(*gen)


def splitall(path):
    r"""Split path into all its componenets

    TODO: tests pass on Windows, not on nix, better way? Not safe to use!
    >> splitall('a/b/c')
    ['a', 'b', 'c']
    >> splitall('/a/b/c/')
    ['/', 'a', 'b', 'c', '']
    >> splitall('/')
    ['/']
    >> splitall('C:')
    ['C:']
    >> splitall('C:\\')
    ['C:\\']
    >> splitall('C:\\a')
    ['C:\\', 'a']
    >> splitall('C:\\a\\')
    ['C:\\', 'a', '']
    >> splitall('C:\\a\\b')
    ['C:\\', 'a', 'b']
    >> splitall('a\\\b')
    ['a', 'b']
    """
    allparts = []
    while True:
        parts = os.path.split(path)
        if parts[0] == path:  # sentinel for absolute paths
            allparts.insert(0, parts[0])
            break
        elif parts[1] == path:   # sentinel for relative paths
            allparts.insert(0, parts[1])
            break
        else:
            path = parts[0]
            allparts.insert(0, parts[1])
    return allparts


def resplit(path, *args):
    r"""Split path by multiple args
    >> path = "/First/Second/Third\\Fourth\\Fifth\\Sixth.txt"
    >> resplit(path, '/', '/', '\\')

    TODO: tests pass on Windows, not on nix, better way? Not safe to use!
    """
    return re.split(r'{}'.format('|'.join(args)), path)


def safe_join(directory, filename):
    """Safely join `directory` and `filename`.  If this cannot be done,
    this function returns ``None``.
    via github.com/mitsuhiko/werkzeug security.py
    """
    _os_alt_seps = [sep for sep in [os.path.sep, os.path.altsep] if sep not in {None, '/'}]
    filename = posixpath.normpath(filename)
    for sep in _os_alt_seps:
        if sep in filename:
            return None
    if os.path.isabs(filename) or filename.startswith('../'):
        return None
    return os.path.join(directory, filename)


if __name__ == '__main__':
    __import__('doctest').testmod()
