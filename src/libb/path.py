import inspect
import os
import pathlib
import sys
from contextlib import contextmanager

__all__ = [
    'add_to_sys_path',
    'cd',
    'get_module_dir',
    'scriptname',
]


def get_module_dir(module=None):
    """Get the directory containing a module.

    :param module: Module to get directory for, defaults to caller's module.
    :returns: Directory path containing the module.
    :rtype: str

    Example::

        etcdir = os.path.join(get_module_dir(), '../../etc')
    """
    if not module:
        # get caller's module
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    return os.path.split(pathlib.Path(module.__file__).resolve())[0]


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
        path = os.path.split(pathlib.Path(module.__file__).resolve())[0]
    if relative_path:
        path = os.path.join(path, relative_path)
    sys.path.insert(0, path)


@contextmanager
def cd(path):
    """Context manager to safely change working directory.

    Restores original directory when context exits.

    :param path: Directory to change to.

    Example::

        with cd("/some/folder"):
            run_command("some_command")
    """
    old_dir = pathlib.Path.cwd()
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
        app, _ = os.path.splitext(pathlib.Path(task).name)
    else:
        app = ''
    return app


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
