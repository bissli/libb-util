"""os.walk and even scandir are miserably slow over network connections in Python 2.
Once you migrate to Python 3, move off glob match to full regex match.
"""
import glob
import itertools
import logging
import os
import random
import shutil
import tempfile
from contextlib import contextmanager
from functools import reduce
from pathlib import Path
from urllib.parse import unquote, urlparse

import backoff
import regex as re
import requests
import tqdm

logger = logging.getLogger(__name__)

__all__ = [
    'mkdir_p',
    'make_tmpdir',
    'expandabspath',
    'get_directory_structure',
    'search',
    'safe_move',
    'save_file_tmpdir',
    'get_dir_match',
    'load_files',
    'load_files_tmpdir',
    'dir_to_dict',
    'download_file',
    'splitall',
    'resplit',
]


def mkdir_p(path):
    Path(path).mkdir(exist_ok=True, parents=True)


@contextmanager
def make_tmpdir(prefix=None) -> Path:
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
    try:
        path = tempfile.mkdtemp(prefix=prefix)
        yield Path(path)
    finally:
        try:
            @backoff.on_exception(backoff.expo, shutil.Error, max_time=10)
            def remove():
                shutil.rmtree(path, ignore_errors=False)
                logger.debug(f'Removed {path}')
            remove()
        except OSError as io:
            logger.error(f'Failed to clean up temp dir {path}')


def expandabspath(p: str) -> str:
    """Expand path to absolute path

    >>> import os
    >>> os.environ['SPAM'] = 'eggs'
    >>> assert expandabspath('~/$SPAM') == os.path.expanduser('~/eggs')
    >>> assert expandabspath('/foo') == '/foo'
    """
    return str(Path(Path(os.path.expandvars(p)).expanduser()).resolve())


def get_directory_structure(rootdir):
    """Creates a nested dictionary that represents the folder structure
    of rootdir
    """
    dir = {}
    rootdir = rootdir.rstrip(os.sep)
    start = rootdir.rfind(os.sep) + 1
    for path, dirs, files in os.walk(rootdir):
        folders = path[start:].split(os.sep)
        subdir = dict.fromkeys(files)
        parent = reduce(dict.get, folders[:-1], dir)
        parent[folders[-1]] = subdir
    return dir


def search(rootdir: str, name : str = None, extension: str = None) -> list:
    """Search for file name, extension, or both (or neither) in directory
    """
    def match(file, s):
        return re.match(fr'.*{s}({Path(file).suffix})?$', file)

    for rootdir, _, files in os.walk(expandabspath(rootdir)):
        for file in files:
            if ((name and match(file, name)) or
                    (extension and Path(file).suffix == extension) or
                    (not name and not extension)):
                yield os.path.join(rootdir, file)


def safe_move(source, target, hard_remove=False):
    """Move a file to a new location, optionally deleting anything in the way"""
    if hard_remove:
        if not Path(target).exists():
            logger.info(f'There is no file to remove at target: {target}')
        else:
            Path(target).unlink()
            logger.info(f'Removed file at target location: {target}')
    try:
        shutil.move(source, target)
    except OSError as err:
        logger.warning('Target already used; adding rendom string to target loc, trying again.')
        targetname, ext = os.path.splitext(target)
        targetname += f'_{random.getrandbits(64):016x}'
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
    with Path(pathname).open('w', encoding='utf-8', errors='ignore') as f:
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
                    logger.debug(themsg)
                    continue
                results.append(fpath)
        else:
            themsg = f'{glob_pattern} NOT FOUND'
            warnings.append(themsg)
            logger.debug(themsg)
    return results, warnings


def load_files(directory, pattern='*', thedate=None):
    files, _ = get_dir_match([(directory, pattern)], thedate)
    logger.info(f'Found {len(files)} matching files in {directory}')
    for pathname in files:
        try:
            with Path(pathname).open(encoding='utf-8', errors='ignore') as f:
                _file = f.read()
            yield _file
        except:
            logger.error(f'{pathname} no longer available...')


def load_files_tmpdir(patterns='*', thedate=None):
    """Get document from temp local store by identifier and date

    >>> import datetime
    >>> patterns = ("nonexistent_pattern_*.txt",)
    >>> results = load_files_tmpdir(patterns, datetime.date.today())
    >>> next(results, None) is None
    True
    """
    tmpdir = tempfile.gettempdir()
    if not isinstance(patterns, list | tuple):
        patterns = (patterns,)
    gen = [load_files(tmpdir, pattern, thedate) for pattern in patterns]
    return itertools.chain(*gen)


def dir_to_dict(path):
    """Convert directory to dict (needs work)
    """
    d = {}
    path = expandabspath(path)
    for i in [os.path.join(path, i) for i in os.listdir(path) if Path(os.path.join(path, i)).is_dir()]:
        d[Path(i).name] = dir_to_dict(i)
    d['.files'] = [i for i in os.listdir(path) if Path(os.path.join(path, i)).is_file()]
    return d


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=30)
def download_file(url, save_path: str | Path = None) -> Path:
    """Better file download from url
    """
    if not save_path:
        name = Path(urlparse(unquote(url)).path).name
        save_path = Path(tempfile.gettempdir()) / name
    else:
        save_path = Path(save_path)
        name = save_path.name
        save_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total = int(r.headers.get('content-length', 0))
        chunk = 16*1024*1024
        with save_path.open('wb') as f, tqdm.tqdm(
            total=total, desc=name, unit='B', unit_scale=True
        ) as p:
            while buf := r.raw.read(chunk):
                f.write(buf)
                p.update(len(buf))
        return save_path


def splitall(path):
    r"""Split path into all its components

    >>> splitall('a/b/c')
    ['a', 'b', 'c']
    >>> splitall('/a/b/c/')
    ['/', 'a', 'b', 'c', '']
    >>> splitall('/')
    ['/']
    >>> splitall('C:')
    ['C:']
    >>> splitall('C:\\')
    ['C:\\']
    >>> splitall('C:\\a')
    ['C:\\', 'a']
    >>> splitall('C:\\a\\')
    ['C:\\', 'a', '']
    >>> splitall('C:\\a\\b')
    ['C:\\', 'a', 'b']
    >>> splitall('a\\\\b')
    ['a', 'b']
    """
    if not isinstance(path, str):
        raise TypeError('Path must be a string')
    if not path:
        return []

    # Handle a possible Windows drive
    drive = ''
    if len(path) >= 2 and path[1] == ':':
        if len(path) == 2:
            # e.g. "C:"
            return [path]
        drive, path = path[:2], path[2:]
        if not path.strip('\\/'):
            # e.g. "C:\" with nothing else
            return [drive + '\\']

    # Convert backslashes to forward slashes for splitting
    path = path.replace('\\', '/')
    path = re.sub(r'/+', '/', path)  # Remove consecutive slashes

    # If the entire path is just "/", return ["/"]
    if path == '/':
        return ['/']

    # Check if it's absolute (leading slash)
    is_absolute = path.startswith('/')

    # Remove leading/trailing slashes for split, then add back empty parts if needed
    core = path.strip('/')
    parts = core.split('/') if core else []
    if path.endswith('/'):
        parts.append('')

    # If it's a drive path, reattach drive
    if drive:
        return [drive + '\\'] + parts

    # If it was absolute (Unix style), prepend "/"
    if is_absolute:
        return ['/'] + parts

    # Otherwise, it's just relative parts
    return parts


def resplit(path, *args):
    r"""Split path by multiple args
    >> path = "/First/Second/Third\\Fourth\\Fifth\\Sixth.txt"
    >> resplit(path, '/', '/', '\\')

    TODO: tests pass on Windows, not on nix, better way? Not safe to use!
    """
    return re.split('|'.join(re.escape(a) for a in args), path)


if __name__ == '__main__':
    __import__('doctest').testmod()
