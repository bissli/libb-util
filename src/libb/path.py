import inspect
import os
import sys
from contextlib import contextmanager
from pathlib import Path

__all__ = [
    'add_to_sys_path',
    'cd',
    'get_module_dir',
    'scriptname',
]


def get_module_dir(module=None) -> Path:
    """Get the directory containing a module.

    :param module: Module to get directory for, defaults to caller's module.
    :returns: Directory path containing the module.
    :rtype: Path

    Example::

        etcdir = get_module_dir() / '../../etc'
    """
    if not module:
        # get caller's module
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    return Path(module.__file__).resolve().parent


def add_to_sys_path(path=None, relative_path=None):
    """Add a path to the Python system search path.

    :param str path: Base path, defaults to calling module's directory.
    :param str relative_path: Relative path to append to base path.

    Example for Unit Tests::

        add_to_sys_path('..')
        import run_task
    """
    if not path:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        path = Path(module.__file__).resolve().parent
    if relative_path:
        path = Path(path) / relative_path
    sys.path.insert(0, str(path))


@contextmanager
def cd(path):
    """Context manager to safely change working directory.

    Restores original directory when context exits.

    :param path: Directory to change to.

    Example::

        with cd("/some/folder"):
            run_command("some_command")
    """
    old_dir = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


def scriptname(task=None):
    """Return name of script being run, without file extension.

    :param str task: Script path, defaults to sys.argv[0].
    :returns: Script name without extension.
    :rtype: str

    Example::

        >>> scriptname(__file__)
        'path'
        >>> scriptname() in sys.argv[0]
        True
        >>> scriptname()==sys.argv[0]
        False
    """
    task = task or sys.argv[0]
    if task:
        app = Path(task).stem
    else:
        app = ''
    return app


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
