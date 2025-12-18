"""Directory and file system utilities.

.. note::
    ``os.walk`` and ``scandir`` were slow over network connections in Python 2.
"""
from __future__ import annotations

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
    """Create directory and any missing parent directories.

    :param path: Directory path to create.

    Example::

        >>> import tempfile, os
        >>> tmpdir = tempfile.mkdtemp()
        >>> newdir = os.path.join(tmpdir, 'a', 'b', 'c')
        >>> mkdir_p(newdir)
        >>> os.path.isdir(newdir)
        True
    """
    Path(path).mkdir(exist_ok=True, parents=True)


@contextmanager
def make_tmpdir(prefix=None) -> Path:
    """Context manager to wrap a temporary directory with auto-cleanup.

    :param str prefix: Optional prefix directory for the temp dir.
    :yields: Path to the temporary directory.

    Example::

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
    prefix = Path(prefix) if prefix else Path(tempfile.gettempdir())
    prefix = str(prefix) + os.sep
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


def expandabspath(p: str) -> Path:
    """Expand path to absolute path with environment variables and user expansion.

    :param str p: Path string to expand.
    :returns: Absolute path with all expansions applied.
    :rtype: Path

    Example::

        >>> import os
        >>> os.environ['SPAM'] = 'eggs'
        >>> assert expandabspath('~/$SPAM') == Path(os.path.expanduser('~/eggs'))
        >>> assert expandabspath('/foo') == Path('/foo')
    """
    return Path(Path(os.path.expandvars(p)).expanduser()).resolve()


def get_directory_structure(rootdir):
    """Create a nested dictionary representing the folder structure.

    :param str rootdir: Root directory to traverse.
    :returns: Nested dictionary of the directory structure.
    :rtype: dict

    Example::

        >>> import tempfile, os
        >>> tmpdir = tempfile.mkdtemp()
        >>> os.makedirs(os.path.join(tmpdir, 'sub'))
        >>> Path(os.path.join(tmpdir, 'file.txt')).touch()
        >>> result = get_directory_structure(tmpdir)
        >>> 'file.txt' in result[os.path.basename(tmpdir)]
        True
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


def search(rootdir: str, name : str = None, extension: str = None):
    """Search for files by name, extension, or both in directory.

    :param str rootdir: Root directory to search.
    :param str name: Optional file name pattern to match.
    :param str extension: Optional file extension to match.
    :yields Path: Full path to each matching file.

    .. seealso::
        See ``tests/test_dir.py`` for usage examples.
    """
    def match(file, s):
        return re.match(fr'.*{s}({Path(file).suffix})?$', file)

    for rootdir, _, files in os.walk(expandabspath(rootdir)):
        for file in files:
            if ((name and match(file, name)) or
                    (extension and Path(file).suffix == extension) or
                    (not name and not extension)):
                yield Path(rootdir) / file


def safe_move(source, target, hard_remove=False) -> Path:
    """Move a file to a new location, optionally deleting anything in the way.

    :param str source: Source file path.
    :param str target: Target file path.
    :param bool hard_remove: If True, delete existing file at target first.
    :returns: Final target path (may differ if conflict occurred).
    :rtype: Path

    .. seealso::
        See ``tests/test_dir.py`` for usage examples.
    """
    target = Path(target)
    if hard_remove:
        if not target.exists():
            logger.info(f'There is no file to remove at target: {target}')
        else:
            target.unlink()
            logger.info(f'Removed file at target location: {target}')
    try:
        shutil.move(source, target)
    except OSError as err:
        logger.warning('Target already used; adding rendom string to target loc, trying again.')
        targetname = target.stem + f'_{random.getrandbits(64):016x}'
        target = target.with_name(targetname + target.suffix)
        shutil.move(source, target)
        logger.warning(f'Succeeded moving to new target: {target}')
    return target


def _append_date(pattern, thedate):
    """Replace date in glob directory match function.

    :param str pattern: File pattern string.
    :param thedate: Date to append/substitute.
    :returns: Pattern with date incorporated.
    :rtype: str

    Example::

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
    """Save a document to the specified temp directory, optionally with date.

    :param str fname: Filename pattern.
    :param str content: Content to write.
    :param thedate: Optional date to append to filename.
    :param kw: Keyword arguments (``tmpdir`` to specify custom temp directory).

    Example::

        >>> import datetime
        >>> content = "</html>...</html>"
        >>> save_file_tmpdir("Foobar.txt", content, thedate=datetime.date.today())
    """
    tmpdir = Path(kw.pop('tmpdir', tempfile.gettempdir()))
    if thedate:
        fname = _append_date(fname, thedate)
    pathname = tmpdir / fname
    with pathname.open('w', encoding='utf-8', errors='ignore') as f:
        f.write(content)
        logger.info(f'Tmp saved {pathname} {fname}')


def get_dir_match(dir_pattern, thedate=None) -> tuple[list[Path], list[str]]:
    """Get paths of existing files matching each glob pattern.

    Filters zero-size files and returns warnings for missing patterns.

    :param dir_pattern: List of (directory, pattern) tuples.
    :param thedate: Optional date to append to patterns.
    :returns: Tuple of (results list of Path objects, warnings list of strings).
    :rtype: tuple[list[Path], list[str]]

    .. seealso::
        See ``tests/test_dir.py`` for usage examples.
    """
    results = []
    warnings = []
    for directory, pattern in dir_pattern:
        if thedate:
            pattern = _append_date(pattern, thedate)
        glob_pattern = Path(directory) / pattern
        files = glob.glob(str(glob_pattern))
        if files:
            for fpath in files:
                fpath = Path(fpath)
                if fpath.stat().st_size == 0:
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
    """Load file contents from directory matching pattern.

    :param str directory: Directory to search.
    :param str pattern: Glob pattern to match files.
    :param thedate: Optional date to append to pattern.
    :yields: File contents as strings.

    .. seealso::
        See ``tests/test_dir.py`` for usage examples.
    """
    files, _ = get_dir_match([(directory, pattern)], thedate)
    logger.info(f'Found {len(files)} matching files in {directory}')
    for pathname in files:
        try:
            with pathname.open(encoding='utf-8', errors='ignore') as f:
                _file = f.read()
            yield _file
        except:
            logger.error(f'{pathname} no longer available...')


def load_files_tmpdir(patterns='*', thedate=None):
    """Load files from temp directory matching patterns.

    :param patterns: Glob pattern(s) to match files.
    :param thedate: Optional date to append to patterns.
    :returns: Iterator of file contents.

    Example::

        >>> import datetime
        >>> patterns = ("nonexistent_pattern_*.txt",)
        >>> results = load_files_tmpdir(patterns, datetime.date.today())
        >>> next(results, None) is None
        True
    """
    tmpdir = tempfile.gettempdir()
    if not isinstance(patterns, (list, tuple)):
        patterns = (patterns,)
    gen = [load_files(tmpdir, pattern, thedate) for pattern in patterns]
    return itertools.chain(*gen)


def dir_to_dict(path):
    """Convert directory structure to a dictionary.

    :param str path: Directory path to convert.
    :returns: Dictionary with subdirectories as nested dicts and ``.files`` key for files.
    :rtype: dict

    Example::

        >>> import tempfile, os
        >>> tmpdir = tempfile.mkdtemp()
        >>> Path(os.path.join(tmpdir, 'test.txt')).touch()
        >>> result = dir_to_dict(tmpdir)
        >>> 'test.txt' in result['.files']
        True
    """
    d = {}
    path = expandabspath(path)
    for item in path.iterdir():
        if item.is_dir():
            d[item.name] = dir_to_dict(item)
    d['.files'] = [item.name for item in path.iterdir() if item.is_file()]
    return d


@backoff.on_exception(backoff.expo, requests.exceptions.RequestException, max_time=30)
def download_file(url, save_path: str | Path = None) -> Path:
    """Download file from URL with progress bar and retry logic.

    :param str url: URL to download from.
    :param save_path: Optional path to save file (defaults to temp directory).
    :type save_path: str or Path
    :returns: Path to downloaded file.
    :rtype: Path

    .. seealso::
        See ``tests/test_dir.py`` for usage examples.
    """
    import tqdm

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
    r"""Split path into all its components.

    Works with both Unix and Windows paths.

    :param str path: Path string to split.
    :returns: List of path components.
    :rtype: list
    :raises TypeError: If path is not a string.

    Example::

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

    drive = ''
    if len(path) >= 2 and path[1] == ':':
        if len(path) == 2:
            # e.g. "C:"
            return [path]
        drive, path = path[:2], path[2:]
        if not path.strip('\\/'):
            # e.g. "C:\" with nothing else
            return [drive + '\\']

    path = path.replace('\\', '/')
    path = re.sub(r'/+', '/', path)  # Remove consecutive slashes

    if path == '/':
        return ['/']

    is_absolute = path.startswith('/')

    core = path.strip('/')
    parts = core.split('/') if core else []
    if path.endswith('/'):
        parts.append('')

    if drive:
        return [drive + '\\'] + parts

    if is_absolute:
        return ['/'] + parts

    return parts


def resplit(path, *args):
    r"""Split path by multiple separators.

    :param str path: Path to split.
    :param args: Separator characters to split on.
    :returns: List of path components.
    :rtype: list

    .. warning::
        Tests pass on Windows, not on nix. Not safe to use!
    """
    return re.split('|'.join(re.escape(a) for a in args), path)


if __name__ == '__main__':
    __import__('doctest').testmod()
