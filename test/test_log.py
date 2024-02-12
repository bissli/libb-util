import logging
import os
import re
import sys

import pytest
from asserts import assert_equal, assert_raises
from libb import config, log


def get_handler_info():
    info = {}
    for h in logging.root.handlers:
        if isinstance(h, logging.FileHandler):
            logfile = os.path.split(h.baseFilename)[-1]
            base, ext = os.path.splitext(logfile)
            bits = [_ for _ in base.split('_') if not re.match(r'\d+', _)]
            appname = '_'.join(bits)
            info['file'] = (logging._levelNames[h.level], logfile, appname)
        elif isinstance(h, (logging.StreamHandler, log.ColoredHandler)):
            info['console'] = (logging._levelNames[h.level], )
        else:
            raise ValueError(h)
    return info


@pytest.mark.skip()
def test_configure_logging_application_default():
    log.configure_logging()
    info = get_handler_info()
    # default is first arg
    app = os.path.splitext(os.path.split(sys.argv[0])[1])[0]
    assert_equal(app, info['file'][2])


@pytest.mark.skip()
def test_configure_logging_application_override():
    log.configure_logging(application='someapp')
    info = get_handler_info()
    assert_equal('someapp', info['file'][2])


@pytest.mark.skip()
def test_configure_logging_environment_default():
    log.configure_logging()
    logcfg = log.LOG_SETUPS[config.ENVIRONMENT]
    # now do some verification of the console and file setup
    # based on this cfg


def test_configure_logging_environment_dev():
    log.configure_logging(setup='dev')
    # do same as above but verify for dev


@pytest.mark.skip()
def test_configure_logging_environment_bad():
    with assert_raises(KeyError):
        log.configure_logging(setup='bad_setup')


@pytest.mark.skip()
def test_configure_logging_level_default():
    log.configure_logging()
    # get cfg from env and levels from cfg and verify with handlers


@pytest.mark.skip()
def test_configure_logging_level_good():
    log.configure_logging(level='warn')
    # do same as above but verify overridden to warn


def test_configure_logging_level_bad():
    with assert_raises(KeyError):
        log.configure_logging(level='bad_level')


def test_set_level_same():
    log.configure_logging(level='info')
    # verify level info
    log.set_level('info')
    # verify same


def test_set_level_good():
    log.configure_logging(level='info')
    log.set_level('warn')
    # verify warn (changed)


def test_set_level_bad():
    log.configure_logging(level='info')
    with assert_raises(KeyError):
        log.set_level('bad_level')


if __name__ == '__main__':
    pytest.main([__file__])
