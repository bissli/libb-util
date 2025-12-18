"""Config related settings, follows 12factor.net."""
from __future__ import annotations

import logging
import os
import tempfile
from abc import ABC
from contextlib import contextmanager
from dataclasses import dataclass, fields
from functools import partial, wraps
from pathlib import Path
from typing import Any

from platformdirs import PlatformDirs

logger = logging.getLogger(__name__)

__all__ = [
    'Setting',
    'ConfigOptions',
    'load_options',
    'configure_environment',
    'patch_library_config',
    'setting_unlocked',
    'get_tempdir',
    'get_vendordir',
    'get_outputdir',
    'get_localdir',
]


class Setting(dict):
    """Dict where ``d['foo']`` can also be accessed as ``d.foo``.

    Automatically creates new sub-attributes of type Setting. This behavior
    can be locked to turn off later.

    .. warning::
        Not copy safe.

    Basic Usage::

        >>> cfg = Setting()
        >>> cfg.unlock() # locked after config.py load
        >>> cfg.foo.bar = 1
        >>> hasattr(cfg.foo, 'bar')
        True
        >>> cfg.foo.bar
        1

    Locking Behavior::

        >>> cfg.lock()
        >>> cfg.foo.bar = 2
        Traceback (most recent call last):
         ...
        ValueError: This Setting object is locked from editing
        >>> cfg.foo.baz = 3
        Traceback (most recent call last):
         ...
        ValueError: This Setting object is locked from editing

    Unlocking::

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
                raise AttributeError(f"Setting object has no attribute '{name}' (locked)")
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
class ConfigOptions(ABC):
    """Abstract base class for loading options from config.py."""

    @classmethod
    def from_config(cls, setting: str, config=None):
        this = config
        for level in setting.split('.'):
            this = getattr(this, level)
        return cls(**this)


def load_options(func=None, *, cls=ConfigOptions):
    """Wrapper that builds dataclass options from config file.

    Standard interface:

    - ``options``: str | dict | ConfigOptions | None
    - ``config``: config module that defines options in ``Settings`` format
    - ``kwargs``: additional kw-args to pass to function

    Setup::

        >>> from libb import Setting, create_mock_module
        >>> Setting.unlock()
        >>> test = Setting()
        >>> test.foo.ftp.host = 'foo'
        >>> test.foo.ftp.user = 'bar'
        >>> test.foo.ftp.pazz = 'baz'
        >>> Setting.lock()
        >>> create_mock_module('test_config', {'test': test})
        >>> import test_config
        >>> @dataclass
        ... class Options(ConfigOptions):
        ...     host: str = None
        ...     user: str = None
        ...     pazz: str = None

    On a Function::

        >>> @load_options(cls=Options)
        ... def testfunc(options=None, config=None, **kwargs):
        ...     return options.host, options.user, options.pazz
        >>> testfunc('test.foo.ftp', config=test_config)
        ('foo', 'bar', 'baz')

    As Simple Kwargs::

        >>> testfunc(host='foo', user='bar', pazz='baz')
        ('foo', 'bar', 'baz')

    On a Class::

        >>> class Test:
        ...     @load_options(cls=Options)
        ...     def __init__(self, options, config, **kwargs):
        ...         self.host = options.host
        ...         self.user = options.user
        ...         self.pazz = options.pazz
        >>> t = Test('test.foo.ftp', test_config)
        >>> t.host, t.user, t.pazz
        ('foo', 'bar', 'baz')
    """
    def _load(options=None, /, config=None, **kwargs):
        if isinstance(options, dict):
            options = cls(**options)
        if isinstance(options, str):
            options = cls.from_config(options, config=config)
        if options is None:
            options = cls(**kwargs)
        for field in fields(cls):
            kwargs.pop(field.name, None)
        return options, config, kwargs

    @wraps(func)
    def func_wrapper(options=None, /, config=None, **kwargs):
        options, config, kw = _load(options, config, **kwargs)
        return func(options, config=config, **kw)

    @wraps(func)
    def class_wrapper(self, options=None, /, config=None, **kwargs):
        options, config, kw = _load(options, config, **kwargs)
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
    """Get temporary directory setting from environment or system default.

    :returns: Setting object with ``dir`` attribute pointing to temp directory.
    :rtype: Setting

    Uses ``CONFIG_TMPDIR_DIR`` environment variable if set, otherwise
    falls back to system temp directory.
    """
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
    """Get vendor directory setting from environment or system default.

    :returns: Setting object with ``dir`` attribute pointing to vendor directory.
    :rtype: Setting

    Uses ``CONFIG_VENDOR_DIR`` environment variable if set, otherwise
    falls back to system temp directory.
    """
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
    """Get output directory setting from environment or system default.

    :returns: Setting object with ``dir`` attribute pointing to output directory.
    :rtype: Setting

    Uses ``CONFIG_OUTPUT_DIR`` environment variable if set, otherwise
    falls back to system temp directory.
    """
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
    """Get local data directory setting using platform-appropriate location.

    :returns: Setting object with ``dir`` attribute pointing to local data directory.
    :rtype: Setting

    Uses platformdirs to determine the appropriate local data directory
    for the current operating system.
    """
    from libb import expandabspath
    local = Setting()
    local.dir = Path(expandabspath(list(__dirs.iter_data_dirs())[0]))
    local.dir = local.dir.as_posix()
    Path(local.dir).mkdir(parents=True, exist_ok=True)
    return local


@contextmanager
def setting_unlocked(setting: Setting):
    """Context manager to safely modify a setting with unlock/lock protection.

    :param Setting setting: The Setting object to unlock/lock.

    Example::

        >>> cfg = Setting()
        >>> cfg.lock()
        >>> with setting_unlocked(cfg):
        ...     cfg.foo = 'bar'
        >>> cfg.foo
        'bar'
        >>> cfg.baz = 'qux'
        Traceback (most recent call last):
         ...
        ValueError: This Setting object is locked from editing
    """
    setting.unlock()
    try:
        yield
    finally:
        setting.lock()


def configure_environment(module, **config_overrides: Any) -> None:
    """Configure environment settings at runtime.

    Dynamically sets configuration values on Setting objects in the provided module.
    Keys should follow the pattern ``setting_attribute`` or ``setting_nested_attribute``.

    :param module: The module containing Setting objects to configure.
    :param config_overrides: Configuration values to set with keys as dotted paths.

    Example::

        >>> from libb import create_mock_module
        >>> Setting.unlock()
        >>> db = Setting()
        >>> db.host = 'localhost'
        >>> Setting.lock()
        >>> create_mock_module('my_config', {'db': db})
        >>> import my_config
        >>> configure_environment(my_config, db_host='remotehost')
        >>> my_config.db.host
        'remotehost'
    """
    for key, value in config_overrides.items():
        parts = key.split('_')

        setting_obj = None
        attr_parts = []

        for i in range(1, len(parts) + 1):
            setting_name = '_'.join(parts[:i])
            if hasattr(module, setting_name):
                setting_obj = getattr(module, setting_name)
                attr_parts = parts[i:]
                break

        logger.debug(f'Processing config key: {key} -> setting_obj found: {setting_obj is not None}')

        if not setting_obj:
            logger.debug(f'No setting object found for key: {key}')
            continue

        if not isinstance(setting_obj, Setting):
            logger.debug(f'Found object for key {key} is not a Setting instance')
            continue

        if not attr_parts:
            logger.debug(f'Key {key} matches setting name exactly, cannot set value')
            continue

        with setting_unlocked(setting_obj):
            target = setting_obj
            for part in attr_parts[:-1]:
                target = getattr(target, part)
                logger.debug(f'Navigated to attribute: {part}')

            logger.debug(f'Setting {key} = {value} on target object')
            setattr(target, attr_parts[-1], value)


def patch_library_config(library_name: str, config_name:str = 'config', **config_overrides: Any) -> None:
    """Patch a library's config module directly in sys.modules.

    Finds and patches the library's config module before the library imports it.
    Works regardless of import order by patching the config module directly.

    :param str library_name: Name of the library whose config should be patched.
    :param str config_name: Name of the config module (default: 'config').
    :param config_overrides: Configuration values to set with keys as dotted paths.

    Example::

        >>> import sys
        >>> from libb import create_mock_module
        >>> Setting.unlock()
        >>> api = Setting()
        >>> api.key = 'oldkey'
        >>> Setting.lock()
        >>> create_mock_module('mylib', {})  # parent module
        >>> create_mock_module('mylib.config', {'api': api})
        >>> patch_library_config('mylib', api_key='newkey')
        >>> sys.modules['mylib.config'].api.key
        'newkey'
    """
    import sys

    config_module_name = f'{library_name}.{config_name}'
    logger.debug(f'Attempting to patch config for library: {library_name}')

    if config_module_name in sys.modules:
        logger.debug(f'Config module {config_module_name} already in sys.modules')
        config_module = sys.modules[config_module_name]
        configure_environment(config_module, **config_overrides)
    else:
        logger.debug(f'Importing config module {config_module_name} for patching')
        try:
            config_module = __import__(config_module_name, fromlist=[''])
            configure_environment(config_module, **config_overrides)
            logger.debug(f'Successfully patched {config_module_name}')
        except ImportError as e:
            logger.debug(f'Failed to import {config_module_name}: {e}')
            raise ImportError(f'Could not import config module {config_module_name}') from e


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
