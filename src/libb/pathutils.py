import inspect
import os
import sys
from contextlib import contextmanager

__all = ['add_to_sys_path', 'cd', 'get_module_dir']


def get_module_dir(module=None):
    """Get the directory of the module. If module is not
    specified, defaults to the caller's module.
    ex:
        etcdir = os.path.join(get_module_dir(), '../../etc')
    """
    if not module:
        # get caller's module
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    return os.path.split(os.path.abspath(module.__file__))[0]


def add_to_sys_path(path=None, relative_path=None):
    """Add a path to the Python system search path.
    If path is not specified, defaults to the calling module's
    directory. If relative_path is specified, it is appended to
    path.
    example for adding path for unit tests:
      add_to_sys_path('..')
      import run_task
    """
    if not path:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
        path = os.path.split(os.path.abspath(module.__file__))[0]
    if relative_path:
        path = os.path.join(path, relative_path)
    sys.path.insert(0, path)


@contextmanager
def cd(path):
    """Safely change working directory and restore when done.
    Usage:

      with cd("/some/folder"):
        run_command("some_command")
    """
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
