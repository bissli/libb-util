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
    """A wrapper class to override the __getattr__ method of a Python module.

    This class allows for the dynamic attribute access of a module, typically
    used for config.py settings. It can look up attributes in an override
    module before falling back to the wrapped module's attributes.

    config.py example:
        self = OverrideModuleGetattr(sys.modules[__name__], local_config)
        sys.modules[__name__] = self

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
    """

    def __init__(self, wrapped: ModuleType, override: ModuleType) -> None:
        self.wrapped = wrapped
        self.override = override

    def __getattr__(self, name):
        """Get the attribute, first looking in the override module and then
        falling back to the wrapped one.
        """
        try:
            env = self.override.ENVIRONMENT
        except AttributeError:
            try:
                env = self.wrapped.ENVIRONMENT
            except:
                pass

        if self.override:
            try:
                return getattr(getattr(self.override, env), name)
            except:
                try:
                    return getattr(self.override, name)
                except:
                    pass
        try:
            return getattr(getattr(self.wrapped, env), name)
        except:
            return getattr(self.wrapped, name)

    def __getitem__(self, name):
        """Allow dynamic module lookups such as config['bloomberg.data']
        """
        bits = name.split('.')
        for bit in bits[:-1]:
            self = self.__getattr__(bit)
        return self.__getattr__(bits[-1])


def get_module(modulename: str) -> ModuleType:
    """A trick to import a dotted module name. This is becasue if you
    call __import__('a.b.c') it really return module a. But by just
    importing it, you can dig out the childmost module from sys.modules.
    """
    __import__(modulename)
    return sys.modules[modulename]


def get_class(classname: str) -> type:
    """Get the class by name. If it has a module prefix, import that module
    and get it from there, otherwise assume it is already in globals.
    """
    if '.' in classname:
        mod, cls = classname.rsplit('.', 1)
        mod = get_module(mod)
        cls = getattr(mod, cls)
    else:
        cls = globals()[classname]
    return cls


def get_subclasses(module: str | ModuleType, parentcls: type) -> list[type]:
    """Get all classes defined in module and subclass of parentcls"""
    if isinstance(module, str):
        module = get_module(module)
    subclasses = []
    for name in dir(module):
        cls = getattr(module, name)
        try:
            if issubclass(cls, parentcls):
                subclasses.append(cls)
        except:
            pass
    return subclasses


def get_function(funcname: str, module: ModuleType | None = None) -> Callable | None:
    """Get a function - in caller module if no module specified"""
    if not module:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    if hasattr(module, funcname):
        return getattr(module, funcname)
    return None


def load_module(name: str, path: str) -> ModuleType:
    """Load module from path

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
    """Patch import module with test_ prefix for specified tables
    executed as
        ```
        mod = patch_load(<module_name>, <funcs>)
        mod.<func_name>(<*params>)
        ```
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
    """Replace source module with our target module

    Assume we are writing a module named sys (danger!!!) and we
    want to import the standard sys into that module.

    For reference
    >>> import sys
    >>> original_sys = sys.modules['sys']

    In code
    >>> _sys = patch_module('sys', '_sys')
    >>> 'sys' in sys.modules
    False
    >>> '_sys' in sys.modules
    True

    For reference
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
    """Create an instance of a class by name.

    >>> instance = create_instance('libb.Setting', foo=42)
    >>> instance.foo
    42
    """
    cls = get_class(classname)
    return cls(*args, **kwargs)


def create_mock_module(modname: str, params: dict[str, Any] | None = None) -> None:
    """Create mock module with set attribute and return value.

    For testing config settings without creating actual config file.

    Basic example
    >>> create_mock_module('foomod', {'x': {'foo': 1, 'bar': 2}})
    >>> import foomod
    >>> foomod.x
    {'foo': 1, 'bar': 2}

    unittest Mock example
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
    """A class representing a virtual module that can have submodules sourced
    from other modules.

    Call from `create_virtual_module`
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
    """Create a virtual module with submodules that are sourced from other
    modules.

    Args:
        modname (str): The name of the virtual module to create.
        submodules (dict): A dictionary mapping submodule names to actual
                           module names.

    Submodule libb into another module
    >>> create_virtual_module('foo', {'libb': 'libb'})
    >>> import foo
    >>> foo.libb.Setting()
    {}

    Create virtual config.py as submodule of foo
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
    """Useful for pytest conftestloading. Works with one or more modules.

    >>> import libb
    >>> _ = get_package_paths_in_module(libb)
    >>> assert 'libb.module' in _
    """
    result = []
    for module in m:
        result.extend(walk_packages(module.__path__, prefix=f'{module.__name__}.'))  # type: ignore
    return result


def get_package_paths_in_module(*m: ModuleType) -> Iterable[str]:
    """Get a list of package paths within the given modules, useful for pytest
    conftest loading.

    Args:
        *m (ModuleType): One or more modules to inspect for package paths.

    Returns
        Iterable[str]: An iterable of package paths as strings.

    Example conftest.py:
        pytest_plugins = [*get_package_paths_in_module(tests.fixtures)]
        # Or multiple modules:
        pytest_plugins = [*get_package_paths_in_module(tests.fixtures, tests.plugins)]
    """
    return [package.name for package in get_packages_in_module(*m)]


def import_non_local(name: str, custom_name: str | None = None) -> ModuleType:
    """Import a module using a custom name to avoid conflicts with local module
    names.

    This function is useful when you have a module with the same name as a
    standard library or third-party module and you want to import the non-local
    one.

    Args:
        name (str): The original module name.
        custom_name (str): The custom name to use for the imported module.

    Returns
        ModuleType: The imported module with the custom name.

    To demonstrate import_non_local, we'll create a mock module named
    'mock_calendar' and then import it using import_non_local with a
    custom name 'std_calendar' to differentiate it from the built-in
    'calendar' module.

    Create a demo mock of calendar (would use actual calendar.py)
    >>> create_mock_module('mock_calendar')
    >>> import mock_calendar
    >>> mock_calendar.isleap = lambda year: year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)

    Now import mock_calendar in place of calendar
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
