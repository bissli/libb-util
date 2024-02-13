import logging
import pathlib

import wrapt

logger = logging.getLogger(__name__)


@wrapt.patch_function_wrapper('mimetypes', 'init')
def patch_mimetypes_init(wrapped, instance, args, kwargs):
    """Patch init known files"""
    knownfiles = pathlib.Path(__file__).parent.absolute() / 'mime.types'
    return wrapped([str(knownfiles)])


from .chart import timeseries
from .cmdline import parse_args
from .collection import *
from .config import Setting
from .date import *
from .dir import *
from .exception import *
from .format import *
from .ftp import connect, sync_site
from .io import *
from .itertools import *
from .log import configure_logging, log_exception
from .mail import *
from .module import *
from .montecarlo import *
from .path import *
from .rand import *
from .signal import *
from .syncd import *
from .text import *
from .thread import *
from .util import *
from .weblib import *
from .win import *
