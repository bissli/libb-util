import sys
import traceback

__all__ = [
    'print_exception',
    'try_else',
]


def print_exception(e, short=True):
    """Print exception traceback with optional verbosity.

    :param Exception e: The exception to print.
    :param bool short: If True, prints only traceback above current frame.

    Example::

        >>> try:
        ...     raise ValueError("example error")
        ... except Exception as e:
        ...     print_exception(e)  # doctest: +SKIP
    """
    if short:
        print('Printing only the traceback above the current stack frame')
        print(''.join(traceback.format_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])))
    else:
        exception_list = traceback.format_stack()
        exception_list = exception_list[:-2]
        exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
        exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))
        exception_str = 'Traceback (most recent call last):\n'
        exception_str += ''.join(exception_list)
        # Removing the last \n
        exception_str = exception_str[:-1]
        print('Printing the full traceback as if we had not caught it here...')
        print(exception_str)


def try_else(func, default=None):
    """Wrap function to return default value if it fails.

    :param func: Function to wrap.
    :param default: Default value or callable to return on failure.
    :returns: Wrapped function.

    Example::

        >>> import json
        >>> d = try_else(json.loads, 2)('{"a": 1, "b": "foo"}')
        >>> d
        {'a': 1, 'b': 'foo'}
        >>> repl = lambda x: 'foobar'
        >>> d = try_else(json.loads, repl)('{"a": 1, b: "foo"}')
        >>> d
        'foobar'
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            if callable(default):
                return default(*args, **kwargs)
            return default

    return wrapper


if __name__ == '__main__':
    __import__('doctest').testmod()
