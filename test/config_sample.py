import sys

from libb import OverrideModuleGetattr, Setting

Setting.unlock()

# default environment
ENVIRONMENT = 'prod'

prod = Setting()
dev = Setting()


def environment(env):
    """Override default environment
    """
    global ENVIRONMENT
    if env:
        ENVIRONMENT = env


main = Setting()
main.main = 'Main'
main.override = 'Main'

import local_config_sample

self = OverrideModuleGetattr(sys.modules[__name__], local_config_sample)
sys.modules[__name__] = self

Setting.lock()
