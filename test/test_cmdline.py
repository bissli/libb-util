import sys

import pytest
from asserts import assert_equal, assert_raises
from libb import cmdline


def test_default_options():
    sys.argv = ['test_cmdline.py']
    opts, args, parser = cmdline.parse_args([], 'usage: foo')
    assert_equal(0, len(args))
    assert_equal(None, opts.environment)
    assert_equal(None, opts.loglevel)
    assert_equal('job', opts.logsetup)
    assert_raises(AttributeError, lambda: opts.badarg)

    sys.argv = ['test_cmdline.py',
                '--environment', 'dev',
                '--loglevel', 'info',
                '--logsetup', 'cmd',
                'foo',
                'bar']
    opts, args, parser = cmdline.parse_args([], 'usage: foo')
    assert_equal(2, len(args))
    assert_equal('foo', args[0])
    assert_equal('bar', args[1])
    assert_equal('dev', opts.environment)
    assert_equal('info', opts.loglevel)
    assert_equal('cmd', opts.logsetup)


def test_custom_options():
    """
    default
    action
    destination
    """
    sys.argv = ['test_cmdline.py',
                '-b',
                '--dest',
                '--value', '10',
                '-s', 'short',
                '--long', 'long',
                'foo',
                'bar']
    opts, args, parser = cmdline.parse_args((
            ('-b', '--boolean', 'A boolean option', False, 'store_true'),
            ('-f', '--default', 'A boolean option', False, 'store_true'),
            ('-d', '--dest', 'An option with different name', True, 'store_false', 'destination'),
            ('-v', '--value', 'A value option'),
            ('-s', None, 'Only a short option'),
            (None, '--long', 'Only a long option'),
            ))
    assert_equal(2, len(args))
    assert_equal('foo', args[0])
    assert_equal('bar', args[1])
    assert_equal(True, opts.boolean)
    assert_equal(False, opts.default)
    assert_equal('10', opts.value)
    assert_equal('short', opts.s)
    assert_equal('long', opts.long)


if __name__ == '__main__':
    pytest.main([__file__])
