import logging
import os
import os.path
import sys
import test.fixtures

import pytest
from libb.module import get_package_paths_in_module

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def pytest_addoption(parser):
    parser.addoption(
        '--log',
        action='store',
        default='INFO',
        help='set logging level',
    )


@pytest.fixture(scope='session')
def logger(request):
    import logging

    loglevel = request.config.getoption('--log')

    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)

    logging.basicConfig()
    logger = logging.getLogger(__name__)
    logger.setLevel(numeric_level)
    return logger


pytest_plugins = [*get_package_paths_in_module(test.fixtures)]
