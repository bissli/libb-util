"""TODO:
- Hander: 'twd_mail' - using defer() in the handler
"""
import copy
import logging
import os
import smtplib
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing, suppress
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from functools import wraps
from logging.config import dictConfig
from logging.handlers import HTTPHandler, SMTPHandler

from libb import config

with suppress(ImportError):
    import web

with suppress(ImportError):
    import mailchimp_transactional as MailchimpTransactional

with suppress(ImportError):
    from twisted.internet import reactor
    from twisted.internet.defer import Deferred
    from twisted.internet.ssl import SSL, ClientContextFactory
    from twisted.mail.smtp import ESMTPSenderFactory


# {{{ Filter

class MachineFilter(logging.Filter):
    def filter(self, record):
        record.machine = socket.gethostname()
        return True


class PreambleFilter(logging.Filter):
    """Write a preamble to a StreamHandler"""

    def __init__(self, app='', args='', setup='',
                 statuses=('succeeded', 'failed'), failno=40):
        self.cmd_app = app
        self.cmd_args = args
        self.cmd_setup = setup
        self._success, self._failure = statuses
        self.cmd_status = self._success
        self.failno = failno

    def filter(self, record):
        record.cmd_app = self.cmd_app
        record.cmd_args = self.cmd_args
        record.cmd_setup = self.cmd_setup
        if record.levelno >= self.failno:
            self.cmd_status = self._failure
        record.cmd_status = self.cmd_status
        return True


class WebServerFilter(logging.Filter):
    """Create a logging.Filter with wsgi webserver context info

    >>> import web  # doctest: +SKIP
    >>> ip_fn = lambda: web.ctx.get('ip')  # doctest: +SKIP
    >>> user_fn = lambda: web.ctx.session.get('user')  # doctest: +SKIP
    >>> handler.addFilter(WebServerFilter(ip_fn, user_fn))  # doctest: +SKIP

    >>> import flask  # doctest: +SKIP
    >>> ip_fn = lambda: flask.request.remote_addr  # doctest: +SKIP
    >>> user_fn = lambda: flask.session.get('user')  # doctest: +SKIP
    >>> handler.addFilter(WebServerFilter(ip_fn, user_fn))  # doctest: +SKIP
    """

    def __init__(self, ip_fn=lambda: '', user_fn=lambda: ''):
        self.ip_fn = ip_fn
        self.user_fn = user_fn

    def filter(self, record):
        ipaddr = self.ip_fn() or ''
        if not ipaddr:
            record.ip = ipaddr
        else:
            try:
                hostname, aliases, _ = socket.gethostbyaddr(ipaddr)
            except OSError:
                hostname = ipaddr
            record.ip = hostname
        record.user = self.user_fn() or ''
        return True

# Filter }}}
# {{{ Handler


def colorize(f):
    """This decorator assumes logging handler with stream
    converts stream to colored output, cross-platform
    """
    @wraps(f)
    def wrapper(*args):
        from libb import console
        logger = args[0]
        record = copy.copy(args[1])
        other_args = args[2:] if len(args) > 2 else []
        levelno = record.levelno
        if not logger.is_tty:  # no access to terminal
            return f(logger, record, *other_args)
        if 'Win' in config.PLATFORM:
            color = console.choose_color_windows(levelno)
        else:
            color = console.choose_color_ansi(levelno)
        with console.set_color(color, stream=logger.stream):
            return f(logger, record, *other_args)
    return wrapper


class NonBufferedFileHandler(logging.FileHandler):
    """Non-buffered version of the standard FileHandler
    closing and reopening the file for each emit
    http://www.python.org/dev/peps/pep-3116/
    adds a preamble if PreambleFilter is enabled
    """

    def __init__(self, filename, mode='a', encoding=None, delay=0):
        super().__init__(filename, mode, encoding, delay)
        self.mode = mode
        self.encoding = encoding
        self.preamble = ('***********************\n'
                         '** Time:  %(asctime)s\n'
                         '** App:   %(cmd_app)s\n'
                         '** Args:  %(cmd_args)s\n'
                         '** Setup: %(cmd_setup)s\n'
                         '***********************\n')

    def emit(self, record):
        if self.stream:
            # calling close() more than once is allowed
            self.stream.close()
        with self._open() as handle:
            self.stream = handle
            if PreambleFilter in self.filters:
                self.stream.write(self.preamble % record)
            super().emit(record)


class ColoredStreamHandler(logging.StreamHandler):
    """coloring stream handler in logging module
    """

    def __init__(self):
        super().__init__()

    @property
    def is_tty(self):
        """No need to colorize output to other processes
        """
        return stream_is_tty(self.stream)

    @property
    def std_or_stderr(self):
        """We only want to do this if we get fileno eq to stdout/err
        """
        fileno = getattr(self.stream, 'fileno', None)
        return fileno and fileno() in {sys.stdout.fileno(), sys.stderr.fileno()}

    @colorize
    def emit(self, record):
        """Calls parent StreamHandler emit after colorizing
        """
        super().emit(record)


class ColoredHandler:
    """Mixin for any logging.Handler trying to generate text and html messages
    """

    def getSubject(self, record):
        subject = self.subject % record.__dict__
        return subject

    def _format_record(self, record):
        color = self._choose_color_html(record.levelno)
        text = self.format(record)
        html = f'<pre style="color:{color};">{text}</pre>'
        return text, html

    def _choose_color_html(self, levelno):
        if levelno >= 40:
            color = '#EE0000'
        elif levelno >= 30:
            color = '#DAA520'
        elif levelno >= 20:
            color = '#228B22'
        elif levelno >= 10:
            color = '#D0D2C4'
        else:
            color = '#000'
        return color


class ColoredSMTPHandler(ColoredHandler, SMTPHandler):
    """emits html-colored email, one per log message .. also formats subject"""

    def __init__(self, *args, **kwargs):
        self.ssl = kwargs.pop('ssl', False)
        super().__init__(*args, **kwargs)

    def emit(self, record):
        try:
            msg = self._build_html_msg(record)
            text, html = self._format_record(record)
            html = f'<html><head></head><body>{html}</body></html>'
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            self._send_html_msg(msg.as_string())
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def _build_html_msg(self, record):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.getSubject(record)
        msg['From'] = self.fromaddr
        msg['To'] = ','.join(self.toaddrs)
        msg['Date'] = formatdate()
        return msg

    def _send_html_msg(self, msg):
        port = self.mailport
        if not port:
            port = smtplib.SMTP_PORT
        if self.ssl:
            smtp = smtplib.SMTP_SSL(self.mailhost, port)
        else:
            smtp = smtplib.SMTP(self.mailhost, port)
        if self.secure is not None:
            smtp.ehlo()
            smtp.starttls(*self.secure)
            smtp.ehlo()
        if self.username:
            smtp.login(self.username, self.password)
        smtp.sendmail(self.fromaddr, self.toaddrs, msg)
        smtp.quit()


class TwistedSMTPHandler:
    """Twisted mixin to make a deferred version of our SMTPHandlers"""

    def _send_html_msg(self, msg):
        port = self.mailport
        if not port:
            port = smtplib.SMTP_PORT
        dfd = Deferred()
        kw = {}
        if self.ssl:
            kw['contextFactory'] = ClientContextFactory()
            kw['contextFactory'].method = SSL.SSLv3_METHOD
        senderFactory = ESMTPSenderFactory(self.username, self.password,
                                           self.fromaddr, self.toaddrs, msg,
                                           dfd, **kw)
        reactor.connectTCP(self.mailhost, port, senderFactory)
        return dfd


class ScreenshotColoredSMTPHandler(ColoredSMTPHandler):
    """== Email context around a failed email scrape ==
    - need to initialize with selenium webdriver or runtime `patch_webdriver`
    - take a screenshot of the current page where an exception was raised
    - also saved the url and page source, for debugging purposes
    """

    def __init__(self, *args, **kwargs):
        self.webdriver = kwargs.pop('webdriver', None)
        super().__init__(*args, **kwargs)

    def _build_html_msg(self, record):
        msg = MIMEMultipart()
        msg['Subject'] = self.getSubject(record)
        msg['From'] = self.fromaddr
        msg['To'] = ','.join(self.toaddrs)
        msg['Date'] = formatdate()
        return msg

    def emit(self, record):
        if self.webdriver is None:
            return
        name = 'screenshot.png'
        src_name = 'page_source.txt'
        try:
            msg = self._build_html_msg(record)
            text, html = self._format_record(record)
            url = self.webdriver.current_url
            lk = f'<div><a href="{url}">{url}</a></div>'
            html = '<html><head></head><body>{}{}<img src="cid:{}"/></body></html>'\
            .format(html, lk, name)
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            img = MIMEBase('image', 'png')
            img.set_payload(self.webdriver.get_screenshot_as_base64())
            img.add_header('Content-ID', name)
            img.add_header('Content-Disposition', 'attachment', filename=name)
            msg.attach(img)
            src = MIMEBase('application', 'octet-stream')
            src.set_payload(self.webdriver.page_source)
            try:
                encoders.encode_base64(src)
            except UnicodeEncodeError:
                page_source_utf = self.webdriver.page_source.encode('utf-8')
                src.set_payload(page_source_utf)
                encoders.encode_base64(src)
            src.add_header('Content-ID', src_name)
            src.add_header('Content-Disposition', 'attachment', filename=src_name)
            msg.attach(src)
            self._send_html_msg(msg.as_string())
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class BufferedColoredSMTPHandler(ColoredSMTPHandler):
    """Get as much of a job log as possible, esp. useful for distributed jobs"""

    def __init__(self, *args, **kwargs):
        capacity = kwargs.pop('capacity', 1024)
        flushLevel = kwargs.pop('flushLevel', logging.ERROR)
        super().__init__(*args, **kwargs)
        self.capacity = capacity
        self.flushLevel = flushLevel
        self.buffer = []

    def shouldFlush(self, record):
        """No longer flushing if we reach flushLevel
        ... otherwise we get bombarded with emails
        """
        return len(self.buffer) >= self.capacity

    def emit(self, record):
        try:
            self.buffer.append(record)
            if self.shouldFlush(record):
                self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

    def flush(self):
        if not self.buffer:
            return
        try:
            msg = self._build_html_msg(self.buffer[-1])  # last msg success/fail
            formatted = [self._format_record(_) for _ in self.buffer]
            text, html = list(zip(*formatted))
            text = '\n'.join(text)
            html = '<html><head></head><body>{}</body></html>'\
            .format('\n'.join(html))
            msg.attach(MIMEText(text, 'text'))
            msg.attach(MIMEText(html, 'html'))
            self._send_html_msg(msg.as_string())
            self.buffer = []
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            for record in self.buffer:
                self.handleError(record)
            self.buffer = []

    def close(self):
        """Final flush before closing the handler"""
        self.flush()
        super().close()


class ColoredMandrillHandler(ColoredHandler, logging.Handler):
    """Send logging emails via Mandrill HTTP API instead of SMTP"""

    def __init__(self, apikey, fromaddr, toaddrs, subject):
        logging.Handler.__init__(self)
        self.api = MailchimpTransactional.Client(apikey)
        self.fromaddr = fromaddr
        if isinstance(toaddrs, str):
            toaddrs = [toaddrs]
        self.toaddrs = [{'email': email} for email in toaddrs]
        self.subject = subject

    def emit(self, record):
        text, html = self._format_record(record)
        msg = {
            'from_email': self.fromaddr,
            'to': self.toaddrs,
            'subject': self.getSubject(record),
            'html': html,
            'text': text,
        }
        try:
            self.api.messages.send({'message':msg})
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class ScreenshotColoredMandrillHandler(ColoredMandrillHandler):
    """Mandrill version of our ScreenshotColoredSMTPHandler"""

    def __init__(self, apikey, fromaddr, toaddrs, subject, **kw):
        self.webdriver = kw.pop('webdriver', None)
        super().__init__(apikey, fromaddr, toaddrs, subject, **kw)

    def emit(self, record):
        if self.webdriver is None:
            return
        name = 'screenshot.png'
        src_name = 'page_source.txt'
        try:
            text, html = self._format_record(record)
            url = self.webdriver.current_url
            lk = f'<div><a href="{url}">{url}</a></div>'
            html = '<html><head></head><body>{}{}<img src="cid:{}"/></body></html>'\
            .format(html, lk, name)
            img = {
                'content': self.webdriver.get_screenshot_as_base64(),
                'name': name,
                'type': 'image/png',
                }
            src = {
                'content': self.webdriver.page_source,
                'name': src_name,
                'type': 'text/plain',
                }
            msg = {
                'from_email': self.fromaddr,
                'to': self.toaddrs,
                'subject': self.getSubject(record),
                'html': html,
                'text': text,
                'images': [img],
                'attachments': [src],
            }
            self.api.messages.send({'message':msg})
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class URLHandler(HTTPHandler):
    """HTTPHandler with HTTPS a SumoLogic headers
    """

    def __init__(self, host, url, method):
        super().__init__()
        self.host = host
        self.url = url
        self.method = method

    def emit(self, record):
        try:
            data = self.format(record)
            with closing(urllib.request.urlopen(self.host+self.url, data)) as req:
                _ = req.read()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


# TODO class logging, stolen from the bowels of sqlalchemy

def _add_default_handler(logger):
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
    logger.addHandler(handler)


_logged_classes = set()


def class_logger(cls, enable=False):
    logger = logging.getLogger(cls.__module__ + '.' + cls.__name__)
    if enable == 'debug':
        logger.setLevel(logging.DEBUG)
    elif enable == 'info':
        logger.setLevel(logging.INFO)
    cls._should_log_debug = lambda self: logger.isEnabledFor(logging.DEBUG)
    cls._should_log_info = lambda self: logger.isEnabledFor(logging.INFO)
    cls.logger = logger
    _logged_classes.add(cls)


# Hanler }}}
# {{{ Config

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
            '()': 'libb.log.MachineFilter',
            },
        'webserver': {
            '()': 'libb.log.WebServerFilter',
            'ip_fn': lambda: web.ctx.get('ip'),
            'user_fn': lambda: hasattr(web.ctx, 'session')
            and web.ctx.session.get('user'),
            },
        'preamble': {
            '()': 'libb.log.PreambleFilter',
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
            'class': 'libb.log.ColoredStreamHandler',
            },
        'job_file': {
            'level': 'INFO',
            'class': 'libb.log.NonBufferedFileHandler',
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

if os.getenv('CONFIG_MANDRILL_APIKEY'):
    # named handlers
    WEB_HANDLERS.extend(['web_mail'])
    JOB_HANDLERS.extend(['job_mail'])
    # handler config
    LOG_CONF['handlers'].update({
        'job_mail': {
            'level': 'ERROR',
            'class': 'libb.log.ColoredMandrillHandler',
            'formatter': 'job_fmt',
            'filters': JOB_FILTERS,
            'apikey': config.mandrill.apikey,
            'fromaddr': config.mail.fromemail,
            'toaddrs': config.mail.toemail,
            'subject': '%(machine)s %(name)s %(levelname)s',
        },
        'web_mail': {
            'level': 'ERROR',
            'class': 'libb.log.ColoredMandrillHandler',
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


# Config }}}


def configure_logging(setup='', app='', app_args=None, level=None):
    """Configure console and file logging for any app"""
    from libb import ismapping, merge_dict, now, scriptname

    if app_args is None:
        app_args = []
    if not app:
        app = scriptname()
        app_args = sys.argv[1:]

    if level:
        set_level(level)

    logconfig = LOG_CONF
    if config.CHECKTTY and stream_is_tty(sys.stdout):
        merge_dict(logconfig, CMD_CONF)
    elif setup == 'cmd':
        merge_dict(logconfig, CMD_CONF)
    elif setup == 'job':
        merge_dict(logconfig, JOB_CONF)
    elif setup == 'twd':
        merge_dict(logconfig, TWD_CONF)

    now = now()
    file_fmt = {
        'app': app,
        'app_args': ' '.join(app_args),
        'setup': setup,
        'date': now.strftime('%Y%m%d'),
        'time': now.strftime('%H%M%S'),
        }

    def file_formatter(thed, str_fmt=file_fmt):
        for k, subd_or_file in thed.items():
            if ismapping(subd_or_file):
                file_formatter(subd_or_file)
            elif k in {'app', 'args', 'filename'}:
                thed[k] = subd_or_file % str_fmt

    file_formatter(logconfig)

    dictConfig(logconfig)


class StderrStreamLogger:
    """Patch over stderr to log print statements to INFO
    placeholders isatty and fileno mimic python stream
    stderr still accessible at stderr.__stderr__
    """

    def __init__(self, logger):
        self.logger = logger
        self.level = logging.INFO
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def isatty(self):
        return False

    def fileno(self):
        return None


def patch_webdriver(this_logger, this_webdriver):
    """Patch logger with SMTP/Mandrill handler
    - for sending webdriver-captured screenshots and errors
    """
    for h in this_logger.handlers:
        if isinstance(h, (ScreenshotColoredSMTPHandler, ScreenshotColoredMandrillHandler)):
            h.webdriver = this_webdriver
            this_logger.warning(f'Patching handler {repr(h)} {logging.getLevelName(h.level)}')


def set_level(levelname):
    """Simple utility for setting root logging via sqla"""
    level_names = {v: k for k, v in logging._levelToName.items()}
    level_names['WARN'] = level_names['WARNING']
    level = level_names[levelname.upper()]
    for handler in logging.root.handlers:
        handler.setLevel(level)
    logging.root.setLevel(level)


def stream_is_tty(somestream):
    """Check if stream, typically sys.stdout, running in terminal"""
    isatty = getattr(somestream, 'isatty', None)
    return isatty and isatty()


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
