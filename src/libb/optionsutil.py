from dataclasses import dataclass, fields
from functools import partial, wraps

__all__ = ['BaseOptions', 'load_options']


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
        options: str | dict | BaseOptions| None:
        config: config module that defines options in `Settings` format
        kwargs: additional kw-args to pass to function

    >>> from libb import config, create_mock_module

    >>> config.Setting.unlock()
    >>> test = config.Setting()
    >>> test.foo.app.foo = 1
    >>> test.foo.app.bar = 2
    >>> test.foo.app.baz = 3
    >>> config.Setting.lock()

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

    """
    @wraps(func)
    def wrapper(options: str | dict | BaseOptions | None = None, config=None, **kw):
        if isinstance(options, dict):
            options = cls(**options)
        if isinstance(options, str):
            options = cls.from_config(options, config=config)
        if options is None:
            options = cls(**kw)
        for field in fields(cls):
            kw.pop(field.name, None)
        return func(options, config=None, **kw)
    if func is None:
        return partial(load_options, cls=cls)
    return wrapper


if __name__ == '__main__':
    __import__('doctest').testmod(optionflags=4 | 8 | 32)
