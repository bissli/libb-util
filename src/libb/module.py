import inspect
import sys
from pkgutil import ModuleInfo, walk_packages
from types import ModuleType
from typing import Iterable


class OverrideModuleGetattr:
    """Class to wrap a Python module and override the
    __getattr__ method so we can hook into 'config.foo'
    module-level variable access.

    Used for config files. To use in a module:

      self = OverrideModuleGetattr(sys.modules[__name__], local_config)
      sys.modules[__name__] = self

    then
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
        """Allow dynamic module lookups such as config['bloomberg.data']"""
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


def create_instance(classname, *args, **kwargs):
    cls = get_class(classname)
    return cls(*args, **kwargs)


def get_packages_in_module(m: ModuleType) -> Iterable[ModuleInfo]:
    return walk_packages(m.__path__, prefix=m.__name__ + '.')  # type: ignore


def get_package_paths_in_module(m: ModuleType) -> Iterable[str]:
    """Useful for pytest conftestloading

    conftest.py:
    pytest_plugins = [*get_package_paths_in_module(tests.fixtures)]
    """
    return [package.name for package in get_packages_in_module(m)]
