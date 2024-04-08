"""Config related settings, follows 12factor.net
"""
import logging
import os
import tempfile
from dataclasses import dataclass, fields
from functools import partial, wraps
from pathlib import Path

from platformdirs import PlatformDirs

logger = logging.getLogger(__name__)

__all__ = [
    'Setting',
    'BaseOptions',
    'load_options',
    'get_tempdir',
    'get_vendordir',
    'get_outputdir',
    'get_localdir',
]


class Setting(dict):
    """Dict where d['foo'] can also be accessed as d.foo
    but also automatically creates new sub-attributes of
    type Setting. This behavior can be locked to turn off
    later. WARNING: not copy safe

    >>> cfg = Setting()
    >>> cfg.unlock() # locked after config.py load

    >>> cfg.foo.bar = 1
    >>> hasattr(cfg.foo, 'bar')
    True
    >>> cfg.foo.bar
    1
    >>> cfg.lock()
    >>> cfg.foo.bar = 2
    Traceback (most recent call last):
     ...
    ValueError: This Setting object is locked from editing
    >>> cfg.foo.baz = 3
    Traceback (most recent call last):
     ...
    ValueError: This Setting object is locked from editing
    >>> cfg.unlock()
    >>> cfg.foo.baz = 3
    >>> cfg.foo.baz
    3
    """

    _locked = False

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)

    def __getattr__(self, name):
        """Create sub-setting fields on the fly"""
        if name not in self:
            if self._locked:
                raise ValueError('This Setting object is locked from editing')
            self[name] = Setting()
        return self[name]

    def __setattr__(self, name, val):
        if self._locked:
            raise ValueError('This Setting object is locked from editing')
        if name not in self:
            self[name] = Setting()
        self[name] = val

    @staticmethod
    def lock():
        Setting._locked = True

    @staticmethod
    def unlock():
        Setting._locked = False


@dataclass
class BaseOptions:
    """Load from config"""

    @classmethod
    def from_config(cls, sitename: str, config=None):
        this = config
        for level in sitename.split('.'):
            this = getattr(this, level)
        return cls(**this)


def load_options(func=None, *, cls=BaseOptions):
    """Wrapper that builds dataclass options from config file.

    Standard interface:
        options: str | dict | BaseOptions| None
        config: config module that defines options in `Settings` format
        kwargs: additional kw-args to pass to function

    >>> from libb import Setting, create_mock_module

    >>> Setting.unlock()
    >>> test = Setting()
    >>> test.foo.app.foo = 1
    >>> test.foo.app.bar = 2
    >>> test.foo.app.baz = 3
    >>> Setting.lock()

    >>> create_mock_module('test_config', {'test': test})
    >>> import test_config

    >>> @dataclass
    ... class Options(BaseOptions):
    ...     foo: int = 0
    ...     bar: int = 0
    ...     baz: int = 0

    >>> @load_options(cls=Options)
    ... def testfunc(options, config, **kw):
    ...     return options.foo, options.bar, options.baz

    >>> testfunc('test.foo.app', test_config)
    (1, 2, 3)

    >>> class Test:
    ...     @load_options(cls=Options)
    ...     def __init__(self, options, config, **kw):
    ...         self.foo = options.foo
    ...         self.bar = options.bar
    ...         self.baz = options.baz
    >>> t = Test('test.foo.app', test_config)
    >>> t.foo, t.bar, t.baz
    (1, 2, 3)
    """
    def _load(options, config=None, **kw):
        if isinstance(options, dict):
            options = cls(**options)
        if isinstance(options, str):
            options = cls.from_config(options, config=config)
        if options is None:
            options = cls(**kw)
        for field in fields(cls):
            kw.pop(field.name, None)
        return options, config, kw
    @wraps(func)
    def func_wrapper(options, config=None, **kw):
        options, config, kw = _load(options, config, **kw)
        return func(options, config=config, **kw)
    @wraps(func)
    def class_wrapper(self, options, config=None, **kw):
        options, config, kw = _load(options, config, **kw)
        return func(self, options, config=config, **kw)
    if func is None:
        return partial(load_options, cls=cls)
    from libb import is_instance_method
    if is_instance_method(func):
        return class_wrapper
    return func_wrapper


__dirs = PlatformDirs(appname='libb', roaming=True)


def iflocked(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        was_locked = False
        if Setting._locked:
            was_locked = True
            Setting.unlock()
        try:
            return func(*args, **kwargs)
        finally:
            if was_locked:
                Setting.lock()
    return wrapper


@iflocked
def get_tempdir() -> Setting:
    from libb import expandabspath
    tmpdir = Setting()
    if os.getenv('CONFIG_TMPDIR_DIR'):
        tmpdir.dir = expandabspath(os.getenv('CONFIG_TMPDIR_DIR'))
    else:
        tmpdir.dir = tempfile.gettempdir()
    Path(tmpdir.dir).mkdir(parents=True, exist_ok=True)
    return tmpdir


@iflocked
def get_vendordir() -> Setting:
    from libb import expandabspath
    vendor = Setting()
    if os.getenv('CONFIG_VENDOR_DIR'):
        vendor.dir = expandabspath(os.getenv('CONFIG_VENDOR_DIR'))
    else:
        vendor.dir = tempfile.gettempdir()
    Path(vendor.dir).mkdir(parents=True, exist_ok=True)
    return vendor


@iflocked
def get_outputdir() -> Setting:
    from libb import expandabspath
    output = Setting()
    if os.getenv('CONFIG_OUTPUT_DIR'):
        output.dir = expandabspath(os.getenv('CONFIG_OUTPUT_DIR'))
    else:
        output.dir = tempfile.gettempdir()
    Path(output.dir).mkdir(parents=True, exist_ok=True)
    return output


@iflocked
def get_localdir() -> Setting:
    from libb import expandabspath
    local = Setting()
    local.dir = Path(expandabspath(list(__dirs.iter_data_dirs())[0]))
    local.dir = local.dir.as_posix()
    Path(local.dir).mkdir(parents=True, exist_ok=True)
    return local


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
