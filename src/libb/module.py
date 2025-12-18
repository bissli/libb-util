from __future__ import annotations

import inspect
import re
import sys
import types
from collections.abc import Callable, Iterable
from importlib import util as importlib_util
from pkgutil import ModuleInfo, walk_packages
from types import ModuleType
from typing import Any

__all__ = [
    'OverrideModuleGetattr',
    'get_module',
    'get_class',
    'get_subclasses',
    'get_function',
    'load_module',
    'patch_load',
    'patch_module',
    'create_instance',
    'create_mock_module',
    'VirtualModule',
    'create_virtual_module',
    'get_packages_in_module',
    'get_package_paths_in_module',
    'import_non_local',
]


class OverrideModuleGetattr:
    """Wrapper to override __getattr__ of a Python module.

    Allows dynamic attribute access for modules, typically used for config.py
    settings. Looks up attributes in an override module before falling back
    to the wrapped module.

    :param wrapped: The original module to wrap.
    :param override: The override module to check first.

    Config.py Example::

        self = OverrideModuleGetattr(sys.modules[__name__], local_config)
        sys.modules[__name__] = self

    Usage Example::

        >>> from libb import Setting
        >>> create_mock_module('config', {'foo': Setting(bar=1)})
        >>> original_config = sys.modules['config']

        >>> override_config = ModuleType('override_config')
        >>> override_config.foo = Setting(bar=2)

        >>> wrapped_config = OverrideModuleGetattr('config', override_config)
        >>> sys.modules['config'] = wrapped_config # important!

        >>> import config
        >>> assert config.foo.bar == 2

        >>> sys.modules['config'] = original_config
        >>> import config
        >>> assert config.foo.bar == 1

        >>> del sys.modules['config']  # cleanup
    """

    def __init__(self, wrapped: ModuleType, override: ModuleType) -> None:
        self.wrapped = wrapped
        self.override = override

    def __getattr__(self, name):
        """Get attribute, checking override module first then wrapped module."""
        env = None
        try:
            env = self.override.ENVIRONMENT
        except AttributeError:
            try:
                env = self.wrapped.ENVIRONMENT
            except AttributeError:
                pass

        if self.override:
            if env is not None:
                try:
                    return getattr(getattr(self.override, env), name)
                except AttributeError:
                    pass
            try:
                return getattr(self.override, name)
            except AttributeError:
                pass
        if env is not None:
            try:
                return getattr(getattr(self.wrapped, env), name)
            except AttributeError:
                pass
        return getattr(self.wrapped, name)

    def __getitem__(self, name):
        """Allow dynamic module lookups like config['bloomberg.data']."""
        bits = name.split('.')
        for bit in bits[:-1]:
            self = self.__getattr__(bit)
        return self.__getattr__(bits[-1])


def get_module(modulename: str) -> ModuleType:
    """Import a dotted module name and return the innermost module.

    Handles the quirk where ``__import__('a.b.c')`` returns module ``a``.

    :param str modulename: Dotted module name to import.
    :returns: The imported module.
    :rtype: ModuleType

    Example::

        >>> m = get_module('libb.module')
        >>> m.__name__
        'libb.module'
    """
    __import__(modulename)
    return sys.modules[modulename]


def get_class(classname: str) -> type:
    """Get a class by its fully qualified name.

    If classname has a module prefix, imports that module first.
    Otherwise assumes the class is already in globals.

    :param str classname: Class name, optionally with module prefix.
    :returns: The class object.
    :rtype: type

    Example::

        >>> cls = get_class('libb.Setting')
        >>> cls.__name__
        'Setting'
    """
    if '.' in classname:
        mod, cls = classname.rsplit('.', 1)
        mod = get_module(mod)
        cls = getattr(mod, cls)
    else:
        cls = globals()[classname]
    return cls


def get_subclasses(module: str | ModuleType, parentcls: type) -> list[type]:
    """Get all classes in a module that are subclasses of parentcls.

    :param module: Module name or module object.
    :param type parentcls: Parent class to check inheritance against.
    :returns: List of subclasses found in the module.
    :rtype: list[type]
    """
    if isinstance(module, str):
        module = get_module(module)
    subclasses = []
    for name in dir(module):
        cls = getattr(module, name)
        try:
            if issubclass(cls, parentcls):
                subclasses.append(cls)
        except TypeError:
            pass
    return subclasses


def get_function(funcname: str, module: ModuleType | None = None) -> Callable | None:
    """Get a function by name from a module.

    :param str funcname: Name of the function.
    :param module: Module to search, defaults to caller's module.
    :returns: The function or None if not found.
    :rtype: Callable or None
    """
    if not module:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    if hasattr(module, funcname):
        return getattr(module, funcname)
    return None


def load_module(name: str, path: str) -> ModuleType:
    """Load a module from a file path.

    :param str name: Name to assign to the module.
    :param str path: Absolute path to the module file.
    :returns: The loaded module.
    :rtype: ModuleType

    Example::

        >>> import os
        >>> m = load_module('module', os.path.abspath(__file__))
        >>> type(m.load_module).__name__
        'function'
        >>> m.load_module.__name__
        'load_module'
    """
    module_spec = importlib_util.spec_from_file_location(name, path)
    module = importlib_util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def patch_load(module_name: str, funcs: list[str], releft: str = '',
               reright: str = '', repl: str = '_', module_name_prefix: str = '') -> ModuleType:
    """Patch and load a module with regex substitutions.

    Useful for replacing function names with test prefixes.

    :param str module_name: Name of the module to load.
    :param list funcs: List of function names to patch.
    :param str releft: Left side of regex pattern.
    :param str reright: Right side of regex pattern.
    :param str repl: Replacement prefix (default: '_').
    :param str module_name_prefix: Prefix for the module name.
    :returns: The patched module.
    :rtype: ModuleType

    Usage::

        mod = patch_load(<module_name>, <funcs>)
        mod.<func_name>(<*params>)
    """
    spec = importlib_util.find_spec(f'{module_name_prefix}{module_name}')
    source = spec.loader.get_source(f'{module_name_prefix}{module_name}')
    source = re.sub(rf"{releft}({'|'.join(funcs)}){reright}", fr'{repl}\1', source)
    module = importlib_util.module_from_spec(spec)
    codeobj = compile(source, module.__spec__.origin, 'exec')
    exec(codeobj, module.__dict__)
    sys.modules[module_name] = module
    return module


def patch_module(source_name: str, target_name: str) -> ModuleType:
    """Replace a source module with a target module in sys.modules.

    Useful when writing a module with the same name as a standard library
    module and needing to import the original.

    :param str source_name: Original module name to replace.
    :param str target_name: New name to assign to the module.
    :returns: The target module.
    :rtype: ModuleType

    Example::

        >>> import sys
        >>> original_sys = sys.modules['sys']

        >>> _sys = patch_module('sys', '_sys')
        >>> 'sys' in sys.modules
        False
        >>> '_sys' in sys.modules
        True

        >>> sys.modules['sys'] = original_sys  # Restore original sys module
    """
    __import__(source_name)
    m = sys.modules.pop(source_name)
    sys.modules[target_name] = m
    target_module = __import__(target_name)
    # move current to end position
    sys.path = sys.path[1:] + sys.path[:1]
    return target_module


def create_instance(classname: str, *args: Any, **kwargs: Any) -> Any:
    """Create an instance of a class by its fully qualified name.

    :param str classname: Fully qualified class name.
    :param args: Positional arguments for the constructor.
    :param kwargs: Keyword arguments for the constructor.
    :returns: Instance of the class.

    Example::

        >>> instance = create_instance('libb.Setting', foo=42)
        >>> instance.foo
        42
    """
    cls = get_class(classname)
    return cls(*args, **kwargs)


def create_mock_module(modname: str, params: dict[str, Any] | None = None) -> None:
    """Create a mock module with specified attributes.

    Useful for testing config settings without creating actual config files.

    :param str modname: Name for the mock module.
    :param dict params: Dictionary of attribute names to values.

    Basic Example::

        >>> create_mock_module('foomod', {'x': {'foo': 1, 'bar': 2}})
        >>> import foomod
        >>> foomod.x
        {'foo': 1, 'bar': 2}

    Unittest Mock Example::

        >>> from unittest.mock import Mock
        >>> mock = Mock(name='foomod.x', return_value='bar')
        >>> create_mock_module('foomod', {'x': mock})
        >>> import foomod
        >>> foomod.x.return_value
        'bar'
    """
    if params is None:
        params = {}
    mock_module = ModuleType(modname)
    sys.modules[modname] = mock_module
    for attr, value in params.items():
        setattr(mock_module, attr, value)


class VirtualModule:
    """Virtual module with submodules sourced from other modules.

    Use via :func:`create_virtual_module`.

    :param str modname: Name for the virtual module.
    :param dict submodules: Mapping of submodule names to actual module names.
    """
    def __init__(self, modname: str, submodules: dict[str, str]) -> None:
        try:
            self._mod = __import__(modname)
        except:
            self._mod = types.ModuleType(modname)
        sys.modules[modname] = self
        __import__(modname)
        self._modname = modname
        self._submodules = submodules

    def __repr__(self):
        return f'Virtual module for {self._modname}'

    def __getattr__(self, attrname):
        if attrname in self._submodules:
            __import__(self._submodules[attrname])
            return sys.modules[self._submodules[attrname]]
        try:
            return self._mod.__dict__[attrname]
        except KeyError:
            raise AttributeError(f"module '{self._modname}' has no attribute '{attrname}'")


def create_virtual_module(modname: str, submodules: dict[str, str]) -> None:
    """Create a virtual module with submodules from other modules.

    :param str modname: Name of the virtual module to create.
    :param dict submodules: Mapping of submodule names to actual module names.

    Submodule Example::

        >>> create_virtual_module('foo', {'libb': 'libb'})
        >>> import foo
        >>> foo.libb.Setting()
        {}

    Virtual Config Example::

        >>> from libb import Setting
        >>> create_mock_module('mock_config', {'ENVIRONMENT': 'prod', 'bar': Setting(baz=1)})
        >>> import mock_config
        >>> create_virtual_module('foo', {'config': 'mock_config'})
        >>> import foo
        >>> foo.config.ENVIRONMENT
        'prod'
        >>> foo.config.bar.baz
        1
    """
    VirtualModule(modname, submodules)


def get_packages_in_module(*m: ModuleType) -> Iterable[ModuleInfo]:
    """Get package info for modules, useful for pytest conftest loading.

    :param m: One or more modules to inspect.
    :returns: Iterable of ModuleInfo objects.
    :rtype: Iterable[ModuleInfo]

    Example::

        >>> import libb
        >>> _ = get_package_paths_in_module(libb)
        >>> assert 'libb.module' in _
    """
    result = []
    for module in m:
        result.extend(walk_packages(module.__path__, prefix=f'{module.__name__}.'))  # type: ignore
    return result


def get_package_paths_in_module(*m: ModuleType) -> Iterable[str]:
    """Get package paths within modules, useful for pytest conftest loading.

    :param m: One or more modules to inspect.
    :returns: Iterable of package path strings.
    :rtype: Iterable[str]

    Conftest.py Example::

        pytest_plugins = [*get_package_paths_in_module(tests.fixtures)]
        # Or multiple modules:
        pytest_plugins = [*get_package_paths_in_module(tests.fixtures, tests.plugins)]
    """
    return [package.name for package in get_packages_in_module(*m)]


def import_non_local(name: str, custom_name: str | None = None) -> ModuleType:
    """Import a module using a custom name to avoid local name conflicts.

    Useful when you have a local module with the same name as a standard
    library or third-party module.

    :param str name: The original module name.
    :param str custom_name: Custom name for the imported module.
    :returns: The imported module with the custom name.
    :rtype: ModuleType
    :raises ModuleNotFoundError: If the module cannot be found.

    Example::

        >>> create_mock_module('mock_calendar')
        >>> import mock_calendar
        >>> mock_calendar.isleap = lambda year: year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

        >>> calendar = import_non_local('calendar', 'mock_calendar')
        >>> 'mock_calendar' in sys.modules
        True
        >>> calendar.isleap(2020)
        True
    """
    custom_name = custom_name or name
    spec = importlib_util.find_spec(name, sys.path[1:])
    if spec is None:
        raise ModuleNotFoundError(f"No module named '{name}'")
    module = importlib_util.module_from_spec(spec)
    sys.modules[custom_name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
