import inspect
import sys
import types
from importlib import util as importlib_util
from pkgutil import ModuleInfo, walk_packages
from types import ModuleType
from typing import Iterable

import regex as re


class OverrideModuleGetattr:
    """Class to wrap a Python module and override the __getattr__ method
    so we can hook into 'config.foo' module-level variable access.

    Used for config files. To use in a module:

      self = OverrideModuleGetattr(sys.modules[__name__], local_config)
      sys.modules[__name__] = self

    See test case example in test_config.py
    """

    def __init__(self, wrapped, override):
        self.wrapped = wrapped
        self.override = override

    def __getattr__(self, name):
        """Get the attribute, first looking in the override
        module and then falling back to the wrapped one.
        """
        try:
            env = self.override.ENVIRONMENT
        except AttributeError:
            env = self.wrapped.ENVIRONMENT

        if self.override:
            try:
                return getattr(getattr(self.override, env), name)
            except (AttributeError, KeyError, ValueError):
                try:
                    return getattr(self.override, name)
                except (AttributeError, KeyError, ValueError):
                    pass
        try:
            return getattr(getattr(self.wrapped, env), name)
        except (AttributeError, KeyError, ValueError):
            return getattr(self.wrapped, name)

    def __getitem__(self, name):
        """Allow dynamic module lookups such as config['bloomberg.data']
        """
        bits = name.split('.')
        for bit in bits[:-1]:
            self = self.__getattr__(bit)
        return self.__getattr__(bits[-1])


def get_module(modulename):
    """A trick to import a dotted module name. This is becasue if you
    call __import__('a.b.c') it really return module a. But by just
    importing it, you can dig out the childmost module from sys.modules.
    """
    __import__(modulename)
    return sys.modules[modulename]


def get_class(classname):
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


def get_subclasses(module, parentcls):
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


def get_function(funcname, module=None):
    """Get a function - in caller module if no module specified"""
    if not module:
        frame = inspect.stack()[1]
        module = inspect.getmodule(frame[0])
    if hasattr(module, funcname):
        return getattr(module, funcname)
    return None


def load_module(name, path):
    """Load module from path

    m = load_module('foo', './foo.py')
    m.bar()

    """
    module_spec = importlib_util.spec_from_file_location(name, path)
    module = importlib_util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def patch_load(module_name: str, funcs: list, releft: str='',
               reright: str='', repl: str='_', module_name_prefix=''):
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


def patch_module(source_name, target_name):
    """Replace source module with our target module

    Assume we are writing a module named platform (danger!!!) and we
    want to import the standard platform into that module.

    In platform.py we would include:

    _platform = patch_module('platform', '_platform')

    _platform would now refer to the current module

    Then I can write "import platform" to import the system
    platform module.

    """
    __import__(source_name)
    m = sys.modules.pop(source_name)
    sys.modules[target_name] = m
    target_module = __import__(target_name)
    # move current to end position
    sys.path = sys.path[1:] + sys.path[:1]
    return target_module


def create_instance(classname, *args, **kwargs):
    cls = get_class(classname)
    return cls(*args, **kwargs)


class VirtualModule:
    def __init__(self, modname, submodules):
        try:
            self._mod = __import__(modname)
        except:
            self._mod = types.ModuleType(modname)
        sys.modules[modname] = self
        __import__(modname)
        self._modname = modname
        self._submodules = submodules

    def __repr__(self):
        return 'Virtual module for ' + self._modname

    def __getattr__(self, attrname):
        if attrname in self._submodules:
            __import__(self._submodules[attrname])
            return sys.modules[self._submodules[attrname]]
        return self._mod.__dict__[attrname]


def create_virtual_module(modname, submodules):
    """Create virtual module with submodule from other module

    >>> import libb
    >>> create_virtual_module('libb', {'new_date': 'libb'})
    >>> import libb
    >>> libb.to_date('2010-01-01')
    Date(2010, 1, 1)
    >>> libb.new_date.to_date('2010-01-01')
    Date(2010, 1, 1)

    >>> import libb
    >>> create_virtual_module('foo', {'date': 'libb'})
    >>> import foo
    >>> foo.date.to_date('2010-01-01')
    Date(2010, 1, 1)

    """
    VirtualModule(modname, submodules)


def get_packages_in_module(m: ModuleType) -> Iterable[ModuleInfo]:
    """Useful for pytest conftestloading
    >>> import libb
    >>> _ = get_package_paths_in_module(libb)
    >>> assert 'libb.module' in _
    """
    return walk_packages(m.__path__, prefix=m.__name__ + '.')  # type: ignore


def get_package_paths_in_module(m: ModuleType) -> Iterable[str]:
    """Useful for pytest conftestloading

    conftest.py:
    pytest_plugins = [*get_package_paths_in_module(tests.fixtures)]
    """
    return [package.name for package in get_packages_in_module(m)]


if __name__ == '__main__':
    __import__('doctest').testmod()
