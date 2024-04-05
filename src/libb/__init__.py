import logging
import pathlib

import wrapt

logger = logging.getLogger(__name__)


@wrapt.patch_function_wrapper('mimetypes', 'init')
def patch_mimetypes_init(wrapped, instance, args, kwargs):
    """Patch init known files"""
    knownfiles = pathlib.Path(__file__).parent.absolute() / 'mime.types'
    return wrapped([str(knownfiles)])


from libb import cmdline, date, ftp, mail
from libb.chart import *
from libb.classutils import *
from libb.config import Setting, expandabspath
from libb.date import *
from libb.dictutils import *
from libb.dir import *
from libb.exception import *
from libb.formatutils import *
from libb.funcutils import *
from libb.io import *
from libb.iterutils import *
from libb.log import *
from libb.mathutils import *
from libb.module import *
from libb.montecarlo import *
from libb.optionsutil import *
from libb.pathutils import *
from libb.procutils import *
from libb.rand import *
from libb.setutils import *
from libb.streamutils import *
from libb.syncd import *
from libb.textutils import *
from libb.thread import *
from libb.util import *
from libb.weblib import *
from libb.win import *
