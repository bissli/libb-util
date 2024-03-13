"""Logging configuration and context
"""

import logging
import os
import ssl
import sys
from contextlib import suppress
from functools import wraps
from logging.config import dictConfig

from libb import config
from libb.log.filters import *
from libb.log.handlers import *
from libb.log.loggers import *

with suppress(ImportError):
    import web

try:
    import mailchimp_transactional as MailchimpTransactional
    MAILCHIMP_ENABLED = True
except ImportError:
    MAILCHIMP_ENABLED = False


__all__ = [
    'configure_logging',
    'log_exception',
    'patch_webdriver',
    'class_logger',
    ]


def set_level(levelname):
    """Simple utility for setting root logging via sqla"""
    level_names = {v: k for k, v in logging._levelToName.items()}
    level_names['WARN'] = level_names['WARNING']
    level = level_names[levelname.upper()]
    for handler in logging.root.handlers:
        handler.setLevel(level)
    logging.root.setLevel(level)


def patch_webdriver(this_logger, this_webdriver):
    """Patch logger with SMTP/Mandrill handler
    - for sending webdriver-captured screenshots and errors
    """
    for h in this_logger.handlers:
        if isinstance(h, (ScreenshotColoredSMTPHandler, ScreenshotColoredMandrillHandler)):
            h.webdriver = this_webdriver
            this_logger.warning(f'Patching handler {repr(h)} {logging.getLevelName(h.level)}')


DEF_FILE_FMT = os.path.join(config.tmpdir.dir, '%(app)s_%(date)s_%(time)s.log')
DEF_JOB_FMT = '%(levelname)-4s %(asctime)s %(machine)s %(name)s %(lineno)d %(message)s'
DEF_WEB_FMT = '%(levelname)-4s %(asctime)s %(machine)s %(name)s %(lineno)d [%(user)s %(ip)s] %(message)s'

WEB_FILTERS = ['machine', 'webserver']
JOB_FILTERS = ['machine', 'preamble']

LOG_CONF = {
    'version': 1,
    'loggers': {},
    'formatters': {
        'job_fmt': {'format': DEF_JOB_FMT},
        'web_fmt': {'format': DEF_WEB_FMT},
        'twd_fmt': {'format': DEF_JOB_FMT},
    },
    'filters': {
        'machine': {
            '()': 'libb.log.filters.MachineFilter',
            },
        'webserver': {
            '()': 'libb.log.filters.WebServerFilter',
            'ip_fn': lambda: web.ctx.get('ip'),
            'user_fn': lambda: hasattr(web.ctx, 'session')
            and web.ctx.session.get('user'),
            },
        'preamble': {
            '()': 'libb.log.filters.PreambleFilter',
            'app': '%(app)s',
            'args': '%(app_args)s',
            'setup': '%(setup)s',
            },
        },
    'handlers': {
        'cmd': {
            'level': 'DEBUG',
            'formatter': 'job_fmt',
            'filters': ['machine'],
            'class': 'libb.log.handlers.ColoredStreamHandler',
            },
        'job_file': {
            'level': 'INFO',
            'class': 'libb.log.handlers.NonBufferedFileHandler',
            'formatter': 'job_fmt',
            'filters': JOB_FILTERS,
            'filename': DEF_FILE_FMT,
            },
        'web_file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'formatter': 'web_fmt',
            'filters': WEB_FILTERS,
            'filename': DEF_FILE_FMT,
            'when': 'D',
            'interval': 1,
            'backupCount': 3,
            },
        },
    }

WEB_HANDLERS = ['web_file']
JOB_HANDLERS = ['job_file']
TWD_HANDLERS = []

if MAILCHIMP_ENABLED and os.getenv('CONFIG_MANDRILL_APIKEY'):
    # named handlers
    WEB_HANDLERS.extend(['web_mail'])
    JOB_HANDLERS.extend(['job_mail'])
    # handler config
    LOG_CONF['handlers'].update({
        'job_mail': {
            'level': 'ERROR',
            'class': 'libb.log.handlers.ColoredMandrillHandler',
            'formatter': 'job_fmt',
            'filters': JOB_FILTERS,
            'apikey': config.mandrill.apikey,
            'fromaddr': config.mail.fromemail,
            'toaddrs': config.mail.toemail,
            'subject': '%(machine)s %(name)s %(levelname)s',
        },
        'web_mail': {
            'level': 'ERROR',
            'class': 'libb.log.handlers.ColoredMandrillHandler',
            'formatter': 'web_fmt',
            'filters': WEB_FILTERS,
            'apikey': config.mandrill.apikey,
            'fromaddr': config.mail.fromemail,
            'toaddrs': config.mail.toemail,
            'subject': '%(machine)s %(name)s %(levelname)s',
        },
    })
if os.getenv('CONFIG_SYSLOG_HOST') and os.getenv('CONFIG_SYSLOG_PORT'):
    # named handlers
    WEB_HANDLERS.extend(['web_sysl'])
    JOB_HANDLERS.extend(['job_sysl'])
    TWD_HANDLERS.extend(['web_sysl'])
    # handler config
    LOG_CONF['handlers'].update({
        'job_sysl': {
            'level': 'INFO',
            'class': 'logging.handlers.SysLogHandler',
            'address': (config.syslog.host, config.syslog.port),
            'formatter': 'job_fmt',
            'filters': JOB_FILTERS,
        },
        'web_sysl': {
            'level': 'INFO',
            'class': 'logging.handlers.SysLogHandler',
            'address': (config.syslog.host, config.syslog.port),
            'formatter': 'web_fmt',
            'filters': WEB_FILTERS,
        },
    })
if os.getenv('CONFIG_TLSSYSLOG_HOST') and os.getenv('CONFIG_TLSSYSLOG_PORT'):
    # named handlers
    WEB_HANDLERS.extend(['web_tlssysl'])
    JOB_HANDLERS.extend(['job_tlssysl'])
    TWD_HANDLERS.extend(['web_tlssysl'])
    # handler config
    LOG_CONF['handlers'].update({
        'job_tlssysl': {
            'level': 'INFO',
            'class': 'tlssyslog.handlers.TLSSysLogHandler',
            'address': (config.tlssyslog.host, config.tlssyslog.port),
            'ssl_kwargs': {
                'cert_reqs': ssl.CERT_REQUIRED,
                'ssl_version': ssl.PROTOCOL_TLS,
                'ca_certs': config.tslsyslog.dir
                },
            'formatter': 'job_fmt',
            'filters': JOB_FILTERS,
        },
        'web_tlssysl': {
            'level': 'INFO',
            'class': 'tlssyslog.handlers.TLSSysLogHandler',
            'address': (config.tlssyslog.host, config.tlssyslog.port),
            'ssl_kwargs': {
                'cert_reqs': ssl.CERT_REQUIRED,
                'ssl_version': ssl.PROTOCOL_TLS,
                'ca_certs': config.tslsyslog.dir
                },
            'formatter': 'web_fmt',
            'filters': WEB_FILTERS,
        },
    })


CMD_CONF = {
    'loggers': {
        'cmd': {
            'handlers': ['cmd'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
CMD_CONF['loggers']['job'] = CMD_CONF['loggers']['cmd']
CMD_CONF['loggers']['twd'] = CMD_CONF['loggers']['cmd']
CMD_CONF['loggers']['web'] = CMD_CONF['loggers']['cmd']

WEB_CONF = {
    'loggers': {
        'web': {
            'handlers': WEB_HANDLERS,
            'level': 'INFO',
            'propagate': True,
        },
    },
}

TWD_CONF = {
    'loggers': {
        'twd': {
            'handlers': TWD_HANDLERS,
            'level': 'INFO',
            'propagate': True,
        },
    },
}

JOB_CONF = {
    'loggers': {
        'job': {
            'handlers': JOB_HANDLERS,
            'level': 'INFO',
            'propagate': True,
        },
    },
}

for mod in (config.log.modules.extra or '').split(','):
    CMD_CONF['loggers'][mod] = CMD_CONF['loggers']['cmd']
    JOB_CONF['loggers'][mod] = JOB_CONF['loggers']['job']
    TWD_CONF['loggers'][mod] = TWD_CONF['loggers']['twd']
    WEB_CONF['loggers'][mod] = WEB_CONF['loggers']['web']


_logged_classes = set()


def class_logger(cls, enable=False):
    """Class logging, stolen from the bowels of sqlalchemy (TODO)
    """
    logger = logging.getLogger(cls.__module__ + '.' + cls.__name__)
    if enable == 'debug':
        logger.setLevel(logging.DEBUG)
    elif enable == 'info':
        logger.setLevel(logging.INFO)
    cls._should_log_debug = lambda self: logger.isEnabledFor(logging.DEBUG)
    cls._should_log_info = lambda self: logger.isEnabledFor(logging.INFO)
    cls.logger = logger
    _logged_classes.add(cls)


def configure_logging(setup='', app='', app_args=None, level=None):
    """Configure console and file logging for any app"""
    from libb import ismapping, merge_dict, now, scriptname, stream_is_tty

    if app_args is None:
        app_args = []
    if not app:
        app = scriptname()
        app_args = sys.argv[1:]

    if level:
        set_level(level)

    logconfig = LOG_CONF

    match setup:
        case 'cmd':
            merge_dict(logconfig, CMD_CONF)
        case 'job':
            merge_dict(logconfig, JOB_CONF)
        case 'twd':
            merge_dict(logconfig, TWD_CONF)
        case 'web':
            merge_dict(logconfig, WEB_CONF)

    if config.CHECKTTY and stream_is_tty(sys.stdout):
        merge_dict(logconfig, CMD_CONF)

    file_fmt = {
        'app': app,
        'app_args': ' '.join(app_args),
        'setup': setup,
        'date': now().strftime('%Y%m%d'),
        'time': now().strftime('%H%M%S'),
        }

    def file_formatter(thed, str_fmt=file_fmt):
        for k, subd_or_file in thed.items():
            if ismapping(subd_or_file):
                file_formatter(subd_or_file)
            elif k in {'app', 'args', 'filename'}:
                thed[k] = subd_or_file % str_fmt

    file_formatter(logconfig)

    dictConfig(logconfig)


def log_exception(logger):
    """Return wrapped function fn in try except and log exception with logger"""
    def wrapper(fn):
        @wraps(fn)
        def wrapped_fn(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                logger.exception(exc)
                raise exc
        return wrapped_fn
    return wrapper


if __name__ == '__main__':
    configure_logging('cmd')
    logger = logging.getLogger('cmd')
    logger.debug('Debug')
    logger.info('Info')
    logger.warning('Warning')
    logger.error('Error')
    logger.critical('Critical')
    try:
        1 / 0
    except Exception as exc:
        logger.exception(exc)
